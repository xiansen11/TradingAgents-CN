import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.database import get_redis_client
from app.services.auth_service import AuthService
from app.services.user_service import user_service

router = APIRouter()
logger = logging.getLogger("webapi.sse")


def _normalize_progress_payload(task_id: str, progress_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(progress_data or {})
    progress_value = payload.get("progress_percentage", payload.get("progress", 0))
    message = payload.get("last_message") or payload.get("message") or ""
    status = payload.get("status", "running")
    current_step_name = payload.get("current_step_name") or ""
    current_step_description = payload.get("current_step_description") or ""
    timestamp = payload.get("last_update") or payload.get("timestamp") or time.time()

    event_type = "progress"
    if status == "completed":
        event_type = "completed"
    elif status == "failed":
        event_type = "failed"
    elif current_step_name:
        event_type = "phase_started"

    payload.update({
        "task_id": task_id,
        "progress": progress_value,
        "progress_percentage": progress_value,
        "message": message,
        "current_step_name": current_step_name,
        "current_step_description": current_step_description,
        "steps": payload.get("steps", []),
        "timestamp": timestamp,
        "live_event": {
            "type": event_type,
            "title": current_step_name or "Analysis in progress",
            "body": current_step_description or message or "Processing latest analysis update",
            "status": status,
            "timestamp": timestamp,
        },
    })
    return payload


async def get_current_stream_user(
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    bearer_token: Optional[str] = None

    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization.split(" ", 1)[1]
    elif token:
        bearer_token = token

    if not bearer_token:
        raise HTTPException(status_code=401, detail="No authorization token")

    token_data = AuthService.verify_token(bearer_token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await user_service.get_user_by_username(token_data.sub)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "name": user.username,
        "is_admin": user.is_admin,
        "roles": ["admin"] if user.is_admin else ["user"],
        "preferences": user.preferences.model_dump() if user.preferences else {},
    }


async def task_progress_generator(task_id: str, user_id: str):
    """Stream Redis progress events for a single A-share analysis task."""
    redis_client = get_redis_client()
    pubsub = None
    channel = f"task_progress:{task_id}"

    try:
        try:
            from app.services.config_provider import provider as config_provider

            effective_settings = await config_provider.get_effective_system_settings()
            poll_timeout = float(effective_settings.get("sse_poll_timeout_seconds", 1.0))
            heartbeat_every = int(effective_settings.get("sse_heartbeat_interval_seconds", 10))
            max_idle_seconds = int(effective_settings.get("sse_task_max_idle_seconds", 300))
        except Exception:
            poll_timeout = float(getattr(settings, "SSE_POLL_TIMEOUT_SECONDS", 1.0))
            heartbeat_every = int(getattr(settings, "SSE_HEARTBEAT_INTERVAL_SECONDS", 10))
            max_idle_seconds = int(getattr(settings, "SSE_TASK_MAX_IDLE_SECONDS", 300))

        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        logger.info("SSE task progress connected: task=%s user=%s", task_id, user_id)
        yield f"event: connected\ndata: {json.dumps({'task_id': task_id, 'message': 'connected', 'timestamp': time.time()}, ensure_ascii=False)}\n\n"

        idle_elapsed = 0.0
        last_heartbeat = time.monotonic()

        while idle_elapsed < max_idle_seconds:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=poll_timeout,
                )
                if message and message["type"] == "message":
                    idle_elapsed = 0.0
                    try:
                        progress_data = json.loads(message["data"])
                    except json.JSONDecodeError:
                        progress_data = {"task_id": task_id, "message": str(message["data"])}

                    normalized_payload = _normalize_progress_payload(task_id, progress_data)
                    yield f"event: progress\ndata: {json.dumps(normalized_payload, ensure_ascii=False)}\n\n"
                else:
                    idle_elapsed += poll_timeout
                    now = time.monotonic()
                    if now - last_heartbeat >= heartbeat_every:
                        payload = {"task_id": task_id, "timestamp": time.time()}
                        yield f"event: heartbeat\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        last_heartbeat = now
            except asyncio.TimeoutError:
                idle_elapsed += poll_timeout
    except Exception as exc:
        logger.exception("SSE task progress error: %s", exc)
        yield f"event: error\ndata: {json.dumps({'error': str(exc), 'task_id': task_id}, ensure_ascii=False)}\n\n"
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(channel)
            except Exception:
                pass
            try:
                await pubsub.close()
            except Exception:
                pass


@router.get("/tasks/{task_id}")
async def stream_task_progress(task_id: str, user: dict = Depends(get_current_stream_user)):
    """Stream real-time progress updates for a single analysis task."""
    return StreamingResponse(
        task_progress_generator(task_id, user["id"]),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
