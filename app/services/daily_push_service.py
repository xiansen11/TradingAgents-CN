from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.database import get_mongo_db
from app.models.analysis import AnalysisParameters, SingleAnalysisRequest
from app.models.daily_push import (
    DailyPushSubscriptionCreate,
    DailyPushSubscriptionUpdate,
    DailyPushRunNowResponse,
    DailyPushRunStartResponse,
)
from app.services.feishu_push_client import (
    FeishuPushClient,
    FeishuPushConfig,
    build_simple_card,
)
from app.services.simple_analysis_service import get_simple_analysis_service

logger = logging.getLogger("webapi")

ACTIVE_STATUSES = {"queued", "generating", "waiting_to_push", "sending"}
TERMINAL_STATUSES = {"sent", "failed"}
DEFAULT_TIMEZONE = "Asia/Shanghai"


class DailyPushService:
    def __init__(self) -> None:
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        db = get_mongo_db()
        await db.daily_push_subscriptions.create_index([("user_id", 1), ("created_at", -1)])
        await db.daily_push_subscriptions.create_index([("enabled", 1), ("next_run_at", 1)])
        await db.daily_push_runs.create_index([("subscription_id", 1), ("created_at", -1)])
        await db.daily_push_runs.create_index([("status", 1), ("updated_at", -1)])
        await db.daily_push_runs.create_index(
            [("subscription_id", 1), ("stock_symbol", 1), ("run_key", 1)],
            unique=True,
        )
        self._indexes_ready = True

    async def list_subscriptions(self, user: Dict[str, Any]) -> List[Dict[str, Any]]:
        await self.ensure_indexes()
        db = get_mongo_db()
        query: Dict[str, Any] = {}
        if not user.get("is_admin"):
            query["user_id"] = str(user["id"])
        cursor = db.daily_push_subscriptions.find(query).sort("created_at", -1)
        return [self._serialize_subscription(doc) async for doc in cursor]

    async def create_subscription(
        self,
        payload: DailyPushSubscriptionCreate,
        user: Dict[str, Any],
    ) -> Dict[str, Any]:
        await self.ensure_indexes()
        now = datetime.utcnow()
        doc = payload.model_dump()
        doc.update(
            {
                "user_id": str(user["id"]),
                "username": user.get("username"),
                "created_at": now,
                "updated_at": now,
                "next_run_at": self._calculate_next_run_at(
                    payload.analysis_time,
                    payload.timezone,
                    now,
                ),
            }
        )
        db = get_mongo_db()
        result = await db.daily_push_subscriptions.insert_one(doc)
        saved = await db.daily_push_subscriptions.find_one({"_id": result.inserted_id})
        return self._serialize_subscription(saved)

    async def update_subscription(
        self,
        subscription_id: str,
        payload: DailyPushSubscriptionUpdate,
        user: Dict[str, Any],
    ) -> Dict[str, Any]:
        await self.ensure_indexes()
        db = get_mongo_db()
        existing = await self._get_subscription_or_raise(subscription_id, user)
        update: Dict[str, Any] = {}

        data = payload.model_dump(exclude_unset=True)
        for key in (
            "name",
            "enabled",
            "stock_symbols",
            "analysis_time",
            "push_time",
            "timezone",
            "analysis_parameters",
        ):
            if key in data and data[key] is not None:
                update[key] = data[key]

        if payload.feishu is not None:
            feishu = dict(existing.get("feishu") or {})
            for key, value in payload.feishu.model_dump(exclude_unset=True).items():
                if value is not None:
                    feishu[key] = value.rstrip("/") if key == "domain" else value
            update["feishu"] = feishu

        if "analysis_time" in update or "timezone" in update:
            update["next_run_at"] = self._calculate_next_run_at(
                update.get("analysis_time") or existing.get("analysis_time", "18:00"),
                update.get("timezone") or existing.get("timezone", DEFAULT_TIMEZONE),
                datetime.utcnow(),
            )

        update["updated_at"] = datetime.utcnow()
        await db.daily_push_subscriptions.update_one(
            {"_id": existing["_id"]},
            {"$set": update},
        )
        saved = await db.daily_push_subscriptions.find_one({"_id": existing["_id"]})
        return self._serialize_subscription(saved)

    async def delete_subscription(self, subscription_id: str, user: Dict[str, Any]) -> None:
        await self.ensure_indexes()
        db = get_mongo_db()
        existing = await self._get_subscription_or_raise(subscription_id, user)
        await db.daily_push_subscriptions.delete_one({"_id": existing["_id"]})

    async def list_runs(
        self,
        user: Dict[str, Any],
        subscription_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        await self.ensure_indexes()
        db = get_mongo_db()
        query: Dict[str, Any] = {}
        if subscription_id:
            query["subscription_id"] = subscription_id
        if status:
            query["status"] = status
        if not user.get("is_admin"):
            query["user_id"] = str(user["id"])

        total = await db.daily_push_runs.count_documents(query)
        cursor = (
            db.daily_push_runs.find(query)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return {
            "items": [self._serialize_run(doc) async for doc in cursor],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def start_test_send(
        self,
        subscription_id: str,
        user: Dict[str, Any],
        stock_symbol: Optional[str] = None,
    ) -> DailyPushRunStartResponse:
        subscription = await self._get_subscription_or_raise(subscription_id, user)
        symbol = stock_symbol or (subscription.get("stock_symbols") or [None])[0]
        if not symbol:
            raise ValueError("subscription does not contain stock symbols")
        if symbol not in subscription.get("stock_symbols", []):
            raise ValueError("stock_symbol must belong to this subscription")
        await self._ensure_no_active_run(str(subscription["_id"]), symbol)
        run = await self._create_run(subscription, symbol, "test")
        task_id = await self._create_analysis_task_for_run(run, subscription, symbol)
        asyncio.create_task(self._execute_run(str(run["_id"]), immediate_send=True))
        return DailyPushRunStartResponse(
            run_id=str(run["_id"]),
            task_id=task_id,
            stock_symbol=symbol,
            status="queued",
        )

    async def start_run_now(
        self,
        subscription_id: str,
        user: Dict[str, Any],
    ) -> DailyPushRunNowResponse:
        subscription = await self._get_subscription_or_raise(subscription_id, user)
        started: List[DailyPushRunStartResponse] = []
        skipped: List[Dict[str, Any]] = []
        for symbol in subscription.get("stock_symbols", []):
            active = await self._find_active_run(str(subscription["_id"]), symbol)
            if active:
                skipped.append(
                    {
                        "stock_symbol": symbol,
                        "reason": "active run exists",
                        "run_id": str(active["_id"]),
                    }
                )
                continue
            run = await self._create_run(subscription, symbol, "manual")
            task_id = await self._create_analysis_task_for_run(run, subscription, symbol)
            asyncio.create_task(self._execute_run(str(run["_id"]), immediate_send=True))
            started.append(
                DailyPushRunStartResponse(
                    run_id=str(run["_id"]),
                    task_id=task_id,
                    stock_symbol=symbol,
                    status="queued",
                )
            )
        return DailyPushRunNowResponse(started=started, skipped=skipped)

    async def dispatch_due_subscriptions(self) -> Dict[str, Any]:
        await self.ensure_indexes()
        db = get_mongo_db()
        now = datetime.utcnow()
        sent_waiting = await self._send_due_waiting_runs(now)
        started = 0
        skipped = 0

        cursor = db.daily_push_subscriptions.find({"enabled": True})
        async for subscription in cursor:
            if not self._is_analysis_due(subscription, now):
                skipped += 1
                continue
            for symbol in subscription.get("stock_symbols", []):
                if await self._scheduled_run_exists(subscription, symbol):
                    continue
                active = await self._find_active_run(str(subscription["_id"]), symbol)
                if active:
                    continue
                try:
                    run = await self._create_run(subscription, symbol, "scheduled")
                    await self._create_analysis_task_for_run(run, subscription, symbol)
                    asyncio.create_task(self._execute_run(str(run["_id"]), immediate_send=False))
                    started += 1
                except DuplicateKeyError:
                    continue
                except Exception as exc:
                    logger.error("Failed to start scheduled daily push run: %s", exc, exc_info=True)

            await db.daily_push_subscriptions.update_one(
                {"_id": subscription["_id"]},
                {
                    "$set": {
                        "next_run_at": self._calculate_next_run_at(
                            subscription.get("analysis_time", "18:00"),
                            subscription.get("timezone", DEFAULT_TIMEZONE),
                            now + timedelta(minutes=1),
                        ),
                        "updated_at": now,
                    }
                },
            )

        return {"started": started, "waiting_sent": sent_waiting, "skipped": skipped}

    async def _send_due_waiting_runs(self, now: datetime) -> int:
        db = get_mongo_db()
        sent = 0
        cursor = db.daily_push_runs.find({"status": "waiting_to_push"})
        async for run in cursor:
            subscription = await db.daily_push_subscriptions.find_one(
                {"_id": self._to_object_id(run["subscription_id"])}
            )
            if not subscription:
                await self._mark_run_failed(run["_id"], "subscription not found")
                continue
            if self._is_push_due(subscription, run.get("run_date"), now):
                asyncio.create_task(self._send_run(str(run["_id"])))
                sent += 1
        return sent

    async def _execute_run(self, run_id: str, immediate_send: bool) -> None:
        db = get_mongo_db()
        run = await db.daily_push_runs.find_one({"_id": self._to_object_id(run_id)})
        if not run:
            return
        subscription = await db.daily_push_subscriptions.find_one(
            {"_id": self._to_object_id(run["subscription_id"])}
        )
        if not subscription:
            await self._mark_run_failed(run["_id"], "subscription not found")
            return

        try:
            await db.daily_push_runs.update_one(
                {"_id": run["_id"]},
                {"$set": {"status": "generating", "started_at": datetime.utcnow(), "updated_at": datetime.utcnow()}},
            )
            task_id = run["task_id"]
            request = self._build_analysis_request(subscription, run["stock_symbol"], run.get("run_date"))
            analysis_service = get_simple_analysis_service()
            await analysis_service.execute_analysis_background(task_id, run["user_id"], request)
            task = await self._wait_for_task_completion(task_id)
            if task and str(task.get("status")) in {"failed", "cancelled"}:
                task_error = task.get("last_error")
                task_result = task.get("result") or {}
                result_error = task_result.get("error") if isinstance(task_result, dict) else None
                raise RuntimeError(task_error or result_error or "analysis task failed")

            report = await self._find_report_for_task(
                task_id,
                expected_analysis_id=self._extract_task_analysis_id(task),
            )
            if not report:
                raise RuntimeError("analysis completed but no report was saved")

            report_id = str(report["_id"])
            await db.daily_push_runs.update_one(
                {"_id": run["_id"]},
                {
                    "$set": {
                        "report_id": report_id,
                        "analysis_id": report.get("analysis_id"),
                        "status": "waiting_to_push",
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            if immediate_send or self._is_push_due(subscription, run.get("run_date"), datetime.utcnow()):
                await self._send_run(run_id)
        except Exception as exc:
            logger.error("Daily push run failed: %s", exc, exc_info=True)
            await self._mark_run_failed(run["_id"], str(exc))

    async def _send_run(self, run_id: str) -> None:
        db = get_mongo_db()
        run = await db.daily_push_runs.find_one({"_id": self._to_object_id(run_id)})
        if not run or run.get("status") in TERMINAL_STATUSES:
            return
        subscription = await db.daily_push_subscriptions.find_one(
            {"_id": self._to_object_id(run["subscription_id"])}
        )
        if not subscription:
            await self._mark_run_failed(run["_id"], "subscription not found")
            return

        try:
            await db.daily_push_runs.update_one(
                {"_id": run["_id"]},
                {"$set": {"status": "sending", "updated_at": datetime.utcnow()}},
            )
            report = await self._load_report(run.get("report_id"), run.get("task_id"))
            if not report:
                raise RuntimeError("report not found")
            card = self._build_report_card(report)
            feishu_config = FeishuPushConfig.from_dict(subscription.get("feishu") or {})
            client = FeishuPushClient(feishu_config)
            response = await client.send_interactive_card(card)
            await db.daily_push_runs.update_one(
                {"_id": run["_id"]},
                {
                    "$set": {
                        "status": "sent",
                        "feishu_response": self._safe_feishu_response(response),
                        "sent_at": datetime.utcnow(),
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
        except Exception as exc:
            logger.error("Daily push send failed: %s", exc, exc_info=True)
            await self._mark_run_failed(run["_id"], str(exc))

    async def _create_run(
        self,
        subscription: Dict[str, Any],
        stock_symbol: str,
        run_type: str,
    ) -> Dict[str, Any]:
        await self.ensure_indexes()
        db = get_mongo_db()
        now = datetime.utcnow()
        run_date = self._local_date(subscription, now).isoformat()
        run_key = run_date if run_type == "scheduled" else f"{run_type}:{now.strftime('%Y%m%d%H%M%S%f')}"
        doc = {
            "subscription_id": str(subscription["_id"]),
            "subscription_name": subscription.get("name"),
            "user_id": subscription.get("user_id"),
            "username": subscription.get("username"),
            "stock_symbol": stock_symbol,
            "run_type": run_type,
            "run_key": run_key,
            "run_date": run_date,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
        }
        result = await db.daily_push_runs.insert_one(doc)
        return await db.daily_push_runs.find_one({"_id": result.inserted_id})

    async def _create_analysis_task_for_run(
        self,
        run: Dict[str, Any],
        subscription: Dict[str, Any],
        stock_symbol: str,
    ) -> str:
        db = get_mongo_db()
        request = self._build_analysis_request(subscription, stock_symbol, run.get("run_date"))
        analysis_service = get_simple_analysis_service()
        try:
            result = await analysis_service.create_analysis_task(run["user_id"], request)
            task_id = result["task_id"]
            await db.daily_push_runs.update_one(
                {"_id": run["_id"]},
                {"$set": {"task_id": task_id, "updated_at": datetime.utcnow()}},
            )
            run["task_id"] = task_id
            return task_id
        except Exception as exc:
            await self._mark_run_failed(run["_id"], str(exc))
            raise

    def _build_analysis_request(
        self,
        subscription: Dict[str, Any],
        stock_symbol: str,
        run_date: Optional[str],
    ) -> SingleAnalysisRequest:
        params = dict(subscription.get("analysis_parameters") or {})
        analysis_date = self._analysis_datetime(run_date)
        return SingleAnalysisRequest(
            symbol=stock_symbol,
            stock_code=stock_symbol,
            parameters=AnalysisParameters(
                market_type="A股",
                analysis_date=analysis_date,
                research_depth=params.get("research_depth") or "标准",
                selected_analysts=params.get("selected_analysts") or ["market", "fundamentals", "news", "social"],
                include_sentiment=True,
                include_risk=True,
                language="zh-CN",
                quick_analysis_model=params.get("quick_analysis_model") or "qwen-turbo",
                deep_analysis_model=params.get("deep_analysis_model") or "qwen-max",
            ),
        )

    async def _find_report_for_task(
        self,
        task_id: str,
        expected_analysis_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        for _ in range(30):
            query_options = [{"task_id": task_id}]
            if expected_analysis_id:
                query_options.append({"analysis_id": expected_analysis_id})
            report = await db.analysis_reports.find_one(
                {"$or": query_options}
            )
            if report:
                return report
            await asyncio.sleep(1)
        task = await db.analysis_tasks.find_one({"task_id": task_id})
        analysis_id = self._extract_task_analysis_id(task)
        if analysis_id:
            return await db.analysis_reports.find_one({"analysis_id": analysis_id})
        return None

    async def _load_report(self, report_id: Optional[str], task_id: Optional[str]) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        if report_id:
            try:
                report = await db.analysis_reports.find_one({"_id": ObjectId(report_id)})
                if report:
                    return report
            except Exception:
                pass
        if task_id:
            return await self._find_report_for_task(task_id)
        return None

    def _build_report_card(self, report: Dict[str, Any]) -> Dict[str, Any]:
        stock_symbol = report.get("stock_symbol") or report.get("stock_code") or ""
        stock_name = report.get("stock_name") or stock_symbol
        analysis_date = report.get("analysis_date") or ""
        recommendation = report.get("recommendation") or "暂无"
        risk_level = report.get("risk_level") or "未知"
        confidence = report.get("confidence_score")
        summary = (report.get("summary") or "报告已生成，请在系统中查看完整内容。").strip()
        key_points = report.get("key_points") or []
        point_lines = "\n".join(f"- {item}" for item in key_points[:6] if item)
        report_url = f"/reports/view/{str(report.get('_id'))}"
        confidence_text = f"{confidence:.2f}" if isinstance(confidence, (int, float)) else "暂无"

        markdown = (
            f"**股票**：{stock_name}({stock_symbol})\n"
            f"**分析日期**：{analysis_date}\n"
            f"**投资建议**：{recommendation}\n"
            f"**信心分**：{confidence_text}\n"
            f"**风险等级**：{risk_level}\n\n"
            f"**核心要点**\n{point_lines or '- 暂无'}\n\n"
            f"**摘要**\n{summary[:1800]}\n\n"
            f"完整报告：{report_url}"
        )
        template = "green" if str(recommendation).lower() in {"buy", "strong_buy", "买入"} else "blue"
        return build_simple_card(
            title=f"{stock_name}({stock_symbol}) 每日股票报告",
            markdown=markdown,
            template=template,
        )

    async def _get_subscription_or_raise(
        self,
        subscription_id: str,
        user: Dict[str, Any],
    ) -> Dict[str, Any]:
        await self.ensure_indexes()
        db = get_mongo_db()
        oid = self._to_object_id(subscription_id)
        doc = await db.daily_push_subscriptions.find_one({"_id": oid})
        if not doc:
            raise ValueError("subscription not found")
        if not user.get("is_admin") and doc.get("user_id") != str(user["id"]):
            raise PermissionError("subscription access denied")
        return doc

    async def _ensure_no_active_run(self, subscription_id: str, stock_symbol: str) -> None:
        active = await self._find_active_run(subscription_id, stock_symbol)
        if active:
            raise ValueError(f"{stock_symbol} already has an active daily push run")

    async def _find_active_run(self, subscription_id: str, stock_symbol: str) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        return await db.daily_push_runs.find_one(
            {
                "subscription_id": subscription_id,
                "stock_symbol": stock_symbol,
                "status": {"$in": list(ACTIVE_STATUSES)},
            }
        )

    async def _scheduled_run_exists(self, subscription: Dict[str, Any], stock_symbol: str) -> bool:
        db = get_mongo_db()
        run_date = self._local_date(subscription, datetime.utcnow()).isoformat()
        existing = await db.daily_push_runs.find_one(
            {
                "subscription_id": str(subscription["_id"]),
                "stock_symbol": stock_symbol,
                "run_type": "scheduled",
                "run_key": run_date,
            }
        )
        return existing is not None

    async def _mark_run_failed(self, run_id: ObjectId, message: str) -> None:
        db = get_mongo_db()
        await db.daily_push_runs.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "status": "failed",
                    "error_message": message[:2000],
                    "completed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    async def _wait_for_task_completion(self, task_id: str, timeout_seconds: int = 10) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        for _ in range(timeout_seconds):
            task = await db.analysis_tasks.find_one({"task_id": task_id})
            if not task:
                await asyncio.sleep(1)
                continue
            if str(task.get("status")) in {"completed", "failed", "cancelled"}:
                return task
            await asyncio.sleep(1)
        return await db.analysis_tasks.find_one({"task_id": task_id})

    def _extract_task_analysis_id(self, task: Optional[Dict[str, Any]]) -> Optional[str]:
        if not task:
            return None
        result = task.get("result") or {}
        if isinstance(result, dict):
            return result.get("analysis_id") or task.get("analysis_id")
        return task.get("analysis_id")

    def _is_analysis_due(self, subscription: Dict[str, Any], now_utc: datetime) -> bool:
        local_now = self._to_local(subscription, now_utc)
        return local_now.time() >= self._parse_time(subscription.get("analysis_time", "18:00"))

    def _is_push_due(self, subscription: Dict[str, Any], run_date: Optional[str], now_utc: datetime) -> bool:
        local_now = self._to_local(subscription, now_utc)
        if run_date and local_now.date().isoformat() > run_date:
            return True
        return local_now.time() >= self._parse_time(subscription.get("push_time", "18:30"))

    def _calculate_next_run_at(self, analysis_time: str, tz_name: str, now_utc: datetime) -> datetime:
        tz = self._zoneinfo(tz_name)
        local_now = now_utc.replace(tzinfo=timezone.utc).astimezone(tz)
        target_time = self._parse_time(analysis_time)
        target = datetime.combine(local_now.date(), target_time, tz)
        if target <= local_now:
            target += timedelta(days=1)
        return target.astimezone(timezone.utc).replace(tzinfo=None)

    def _local_date(self, subscription: Dict[str, Any], now_utc: datetime) -> date:
        return self._to_local(subscription, now_utc).date()

    def _to_local(self, subscription: Dict[str, Any], now_utc: datetime) -> datetime:
        tz = self._zoneinfo(subscription.get("timezone") or DEFAULT_TIMEZONE)
        return now_utc.replace(tzinfo=timezone.utc).astimezone(tz)

    def _zoneinfo(self, tz_name: str) -> ZoneInfo:
        try:
            return ZoneInfo(tz_name or DEFAULT_TIMEZONE)
        except ZoneInfoNotFoundError:
            return ZoneInfo(DEFAULT_TIMEZONE)

    def _parse_time(self, value: str) -> time:
        hour, minute = str(value or "18:00").split(":", 1)
        return time(hour=int(hour), minute=int(minute))

    def _analysis_datetime(self, run_date: Optional[str]) -> datetime:
        if run_date:
            try:
                return datetime.strptime(run_date, "%Y-%m-%d")
            except ValueError:
                pass
        return datetime.utcnow()

    def _serialize_subscription(self, doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not doc:
            return {}
        feishu = dict(doc.get("feishu") or {})
        app_secret = feishu.pop("app_secret", None)
        feishu["has_app_secret"] = bool(app_secret)
        return self._jsonable({**doc, "id": str(doc["_id"]), "feishu": feishu})

    def _serialize_run(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return self._jsonable({**doc, "id": str(doc["_id"])})

    def _jsonable(self, value: Any) -> Any:
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: self._jsonable(item) for key, item in value.items() if key != "_id"}
        if isinstance(value, list):
            return [self._jsonable(item) for item in value]
        return value

    def _safe_feishu_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        safe = dict(response or {})
        for key in list(safe.keys()):
            if any(token in key.lower() for token in ("token", "secret", "password")):
                safe[key] = "***"
        return safe

    def _to_object_id(self, value: str) -> ObjectId:
        try:
            return ObjectId(value)
        except Exception as exc:
            raise ValueError("invalid object id") from exc


_daily_push_service: Optional[DailyPushService] = None


def get_daily_push_service() -> DailyPushService:
    global _daily_push_service
    if _daily_push_service is None:
        _daily_push_service = DailyPushService()
    return _daily_push_service
