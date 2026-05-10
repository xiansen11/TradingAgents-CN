from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import asyncio
import json
import logging
import time

from app.routers.auth_db import get_current_user
from app.core.database import get_redis_client
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger("webapi.sse")


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
      yield f"event: connected\ndata: {json.dumps({'task_id': task_id, 'message': '已连接进度流'}, ensure_ascii=False)}\n\n"

      idle_elapsed = 0.0
      last_heartbeat = time.monotonic()

      while idle_elapsed < max_idle_seconds:
          try:
              message = await asyncio.wait_for(
                  pubsub.get_message(ignore_subscribe_messages=True),
                  timeout=poll_timeout
              )
              if message and message["type"] == "message":
                  idle_elapsed = 0.0
                  try:
                      progress_data = json.loads(message["data"])
                  except json.JSONDecodeError:
                      progress_data = {"task_id": task_id, "message": str(message["data"])}
                  yield f"event: progress\ndata: {json.dumps(progress_data, ensure_ascii=False)}\n\n"
              else:
                  idle_elapsed += poll_timeout
                  now = time.monotonic()
                  if now - last_heartbeat >= heartbeat_every:
                      payload = {"task_id": task_id, "timestamp": now}
                      yield f"event: heartbeat\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                      last_heartbeat = now
          except asyncio.TimeoutError:
              idle_elapsed += poll_timeout
    except Exception as exc:
        logger.exception("SSE task progress error: %s", exc)
        yield f"event: error\ndata: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
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
async def stream_task_progress(task_id: str, user: dict = Depends(get_current_user)):
    """Stream real-time progress updates for a single analysis task."""
    return StreamingResponse(
        task_progress_generator(task_id, user["id"]),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
