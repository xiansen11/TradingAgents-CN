from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.response import ok
from app.models.daily_push import (
    DailyPushSubscriptionCreate,
    DailyPushSubscriptionUpdate,
    DailyPushTestSendRequest,
)
from app.routers.auth_db import get_current_user
from app.services.daily_push_service import DailyPushService, get_daily_push_service

router = APIRouter(prefix="/api/daily-push", tags=["daily-push"])


def _handle_service_error(exc: Exception) -> None:
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc))
    raise HTTPException(status_code=500, detail=str(exc))


@router.get("/subscriptions")
async def list_subscriptions(
    user: dict = Depends(get_current_user),
    service: DailyPushService = Depends(get_daily_push_service),
):
    try:
        return ok(data=await service.list_subscriptions(user), message="subscriptions loaded")
    except Exception as exc:
        _handle_service_error(exc)


@router.post("/subscriptions")
async def create_subscription(
    payload: DailyPushSubscriptionCreate,
    user: dict = Depends(get_current_user),
    service: DailyPushService = Depends(get_daily_push_service),
):
    try:
        return ok(data=await service.create_subscription(payload, user), message="subscription created")
    except Exception as exc:
        _handle_service_error(exc)


@router.put("/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: str,
    payload: DailyPushSubscriptionUpdate,
    user: dict = Depends(get_current_user),
    service: DailyPushService = Depends(get_daily_push_service),
):
    try:
        return ok(
            data=await service.update_subscription(subscription_id, payload, user),
            message="subscription updated",
        )
    except Exception as exc:
        _handle_service_error(exc)


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    user: dict = Depends(get_current_user),
    service: DailyPushService = Depends(get_daily_push_service),
):
    try:
        await service.delete_subscription(subscription_id, user)
        return ok(message="subscription deleted")
    except Exception as exc:
        _handle_service_error(exc)


@router.post("/subscriptions/{subscription_id}/test-send")
async def test_send(
    subscription_id: str,
    payload: DailyPushTestSendRequest,
    user: dict = Depends(get_current_user),
    service: DailyPushService = Depends(get_daily_push_service),
):
    try:
        result = await service.start_test_send(subscription_id, user, payload.stock_symbol)
        return ok(data=result.model_dump(), message="test send started")
    except Exception as exc:
        _handle_service_error(exc)


@router.post("/subscriptions/{subscription_id}/run-now")
async def run_now(
    subscription_id: str,
    user: dict = Depends(get_current_user),
    service: DailyPushService = Depends(get_daily_push_service),
):
    try:
        result = await service.start_run_now(subscription_id, user)
        return ok(data=result.model_dump(), message="daily push run started")
    except Exception as exc:
        _handle_service_error(exc)


@router.get("/runs")
async def list_runs(
    subscription_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    service: DailyPushService = Depends(get_daily_push_service),
):
    try:
        return ok(
            data=await service.list_runs(
                user=user,
                subscription_id=subscription_id,
                status=status,
                limit=limit,
                offset=offset,
            ),
            message="runs loaded",
        )
    except Exception as exc:
        _handle_service_error(exc)
