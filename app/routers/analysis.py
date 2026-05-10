"""
A股单股分析 API 路由。

精简版只保留单股分析任务、进度/结果查询、历史和删除能力。
外围分析入口已移除，仅保留 A 股单股分析任务。
"""

from __future__ import annotations

from datetime import datetime
import logging
import re
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.core.database import get_mongo_db
from app.models.analysis import AnalysisParameters, SingleAnalysisRequest
from app.routers.auth_db import get_current_user
from app.services.simple_analysis_service import get_simple_analysis_service
from app.services.websocket_manager import get_websocket_manager

router = APIRouter()
logger = logging.getLogger("webapi")

A_STOCK_PATTERN = re.compile(r"^\d{6}$")


def _normalize_symbol(symbol: Optional[str]) -> str:
    return str(symbol or "").strip()


def _ensure_a_stock(symbol: str) -> None:
    if not A_STOCK_PATTERN.fullmatch(symbol):
        raise HTTPException(status_code=400, detail="精简版仅支持 6 位数字 A股代码")


def _normalize_request(request: SingleAnalysisRequest) -> SingleAnalysisRequest:
    symbol = _normalize_symbol(request.get_symbol())
    _ensure_a_stock(symbol)

    params = request.parameters or AnalysisParameters()
    params.market_type = "A股"
    params.language = "zh-CN"

    request.symbol = symbol
    request.stock_code = symbol
    request.parameters = params
    return request


def _jsonable(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _build_report_query(report_id: str) -> Dict[str, Any]:
    conditions: List[Dict[str, Any]] = [
        {"task_id": report_id},
        {"analysis_id": report_id},
    ]
    try:
        conditions.append({"_id": ObjectId(report_id)})
    except Exception:
        pass
    return {"$or": conditions}


def _build_status_from_task(task_id: str, task_doc: Dict[str, Any]) -> Dict[str, Any]:
    status = task_doc.get("status", "pending")
    progress = task_doc.get("progress", 0)
    started_at = task_doc.get("started_at") or task_doc.get("created_at")
    completed_at = task_doc.get("completed_at")

    elapsed_time = 0
    if isinstance(started_at, datetime):
        end_time = completed_at if isinstance(completed_at, datetime) else datetime.utcnow()
        elapsed_time = max(0, (end_time - started_at).total_seconds())

    symbol = task_doc.get("symbol") or task_doc.get("stock_code") or task_doc.get("stock_symbol")
    return {
        "task_id": task_id,
        "status": status,
        "progress": progress,
        "message": task_doc.get("message") or f"任务{status}",
        "current_step": task_doc.get("current_step") or status,
        "start_time": started_at,
        "end_time": completed_at,
        "elapsed_time": elapsed_time,
        "remaining_time": task_doc.get("remaining_time", 0),
        "estimated_total_time": task_doc.get("estimated_total_time", 0),
        "symbol": symbol,
        "stock_code": symbol,
        "stock_symbol": symbol,
        "steps": task_doc.get("steps", []),
        "source": "analysis_tasks",
    }


def _build_status_from_report(task_id: str, report_doc: Dict[str, Any]) -> Dict[str, Any]:
    symbol = report_doc.get("stock_symbol")
    created_at = report_doc.get("created_at")
    updated_at = report_doc.get("updated_at")
    elapsed_time = 0
    if isinstance(created_at, datetime) and isinstance(updated_at, datetime):
        elapsed_time = max(0, (updated_at - created_at).total_seconds())

    return {
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "message": "分析完成",
        "current_step": "completed",
        "start_time": created_at,
        "end_time": updated_at,
        "elapsed_time": elapsed_time,
        "remaining_time": 0,
        "estimated_total_time": elapsed_time,
        "symbol": symbol,
        "stock_code": symbol,
        "stock_symbol": symbol,
        "analysts": report_doc.get("analysts", []),
        "research_depth": report_doc.get("research_depth", "标准"),
        "source": "analysis_reports",
    }


async def _load_status_from_mongo(task_id: str) -> Optional[Dict[str, Any]]:
    db = get_mongo_db()
    task_doc = await db.analysis_tasks.find_one({"task_id": task_id})
    if task_doc:
        return _build_status_from_task(task_id, task_doc)

    report_doc = await db.analysis_reports.find_one(_build_report_query(task_id))
    if report_doc:
        return _build_status_from_report(task_id, report_doc)

    return None


def _build_result_from_report(report_doc: Dict[str, Any]) -> Dict[str, Any]:
    symbol = report_doc.get("stock_symbol")
    return {
        "analysis_id": report_doc.get("analysis_id"),
        "task_id": report_doc.get("task_id"),
        "stock_symbol": symbol,
        "stock_code": symbol,
        "stock_name": report_doc.get("stock_name", symbol),
        "market_type": "A股",
        "analysis_date": report_doc.get("analysis_date"),
        "summary": report_doc.get("summary", ""),
        "recommendation": report_doc.get("recommendation", ""),
        "confidence_score": report_doc.get("confidence_score", 0.0),
        "risk_level": report_doc.get("risk_level", "中等"),
        "key_points": report_doc.get("key_points", []),
        "execution_time": report_doc.get("execution_time", 0),
        "tokens_used": report_doc.get("tokens_used", 0),
        "analysts": report_doc.get("analysts", []),
        "research_depth": report_doc.get("research_depth", "标准"),
        "reports": report_doc.get("reports", {}),
        "decision": report_doc.get("decision", {}),
        "performance_metrics": report_doc.get("performance_metrics", {}),
        "created_at": report_doc.get("created_at"),
        "updated_at": report_doc.get("updated_at"),
        "status": report_doc.get("status", "completed"),
        "source": "analysis_reports",
    }


async def _load_result_from_mongo(task_id: str) -> Optional[Dict[str, Any]]:
    db = get_mongo_db()
    report_doc = await db.analysis_reports.find_one(_build_report_query(task_id))
    if report_doc:
        return _build_result_from_report(report_doc)

    task_doc = await db.analysis_tasks.find_one({"task_id": task_id})
    if task_doc and task_doc.get("result"):
        result = task_doc["result"]
        symbol = task_doc.get("symbol") or task_doc.get("stock_code") or result.get("stock_symbol") or result.get("stock_code")
        result.setdefault("task_id", task_id)
        result.setdefault("stock_symbol", symbol)
        result.setdefault("stock_code", symbol)
        result.setdefault("market_type", "A股")
        result.setdefault("source", "analysis_tasks")
        return result

    return None


@router.post("/single", response_model=Dict[str, Any])
async def submit_single_analysis(
    request: SingleAnalysisRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """创建 A股单股分析任务，并在后台执行多智能体分析。"""
    normalized_request = _normalize_request(request)

    try:
        analysis_service = get_simple_analysis_service()
        result = await analysis_service.create_analysis_task(user["id"], normalized_request)
        task_id = result["task_id"]
        user_id = user["id"]

        async def run_analysis_task() -> None:
            try:
                service = get_simple_analysis_service()
                await service.execute_analysis_background(task_id, user_id, normalized_request)
                logger.info("A股单股分析任务完成: %s", task_id)
            except Exception as exc:
                logger.error("A股单股分析任务失败: %s - %s", task_id, exc, exc_info=True)

        background_tasks.add_task(run_analysis_task)

        return {
            "success": True,
            "data": result,
            "message": "分析任务已在后台启动",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("提交单股分析任务失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/tasks/{task_id}/status", response_model=Dict[str, Any])
async def get_task_status(task_id: str, user: dict = Depends(get_current_user)):
    """查询分析任务状态，优先读取内存/Redis 进度，兜底读取 MongoDB。"""
    try:
        analysis_service = get_simple_analysis_service()
        status_data = await analysis_service.get_task_status(task_id)
        if not status_data:
            status_data = await _load_status_from_mongo(task_id)
        if not status_data:
            raise HTTPException(status_code=404, detail="任务不存在")

        return {
            "success": True,
            "data": _jsonable(status_data),
            "message": "任务状态获取成功",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("获取任务状态失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tasks/{task_id}/result", response_model=Dict[str, Any])
async def get_task_result(task_id: str, user: dict = Depends(get_current_user)):
    """查询分析任务结果。"""
    try:
        analysis_service = get_simple_analysis_service()
        status_data = await analysis_service.get_task_status(task_id)
        result_data = None

        if status_data and status_data.get("status") == "completed":
            result_data = status_data.get("result_data") or status_data.get("result")

        if not result_data:
            result_data = await _load_result_from_mongo(task_id)

        if not result_data:
            raise HTTPException(status_code=404, detail="分析结果不存在")

        return {
            "success": True,
            "data": _jsonable(result_data),
            "message": "分析结果获取成功",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("获取任务结果失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tasks", response_model=Dict[str, Any])
async def list_user_tasks(
    user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """查询当前用户的单股分析任务。"""
    try:
        analysis_service = get_simple_analysis_service()
        tasks = await analysis_service.list_user_tasks(user["id"], status=status, limit=limit, offset=offset)
        return {
            "success": True,
            "data": _jsonable(tasks),
            "message": "任务列表获取成功",
        }
    except Exception as exc:
        logger.error("获取任务列表失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/user/history", response_model=Dict[str, Any])
async def get_user_analysis_history(
    user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    stock_code: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """查询当前用户的 A股单股分析历史。"""
    query: Dict[str, Any] = {"market_type": "A股"}
    code = symbol or stock_code
    if code:
        code = _normalize_symbol(code)
        _ensure_a_stock(code)
        query["stock_symbol"] = code
    if status:
        query["status"] = status
    if start_date or end_date:
        date_query: Dict[str, str] = {}
        if start_date:
            date_query["$gte"] = start_date
        if end_date:
            date_query["$lte"] = end_date
        query["analysis_date"] = date_query

    try:
        db = get_mongo_db()
        total = await db.analysis_reports.count_documents(query)
        cursor = (
            db.analysis_reports.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        analyses = []
        async for doc in cursor:
            analyses.append(_build_result_from_report(doc))

        return {
            "success": True,
            "data": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "analyses": _jsonable(analyses),
            },
            "message": "分析历史获取成功",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("获取分析历史失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/tasks/{task_id}", response_model=Dict[str, Any])
async def delete_task(task_id: str, user: dict = Depends(get_current_user)):
    """删除单股分析任务及对应报告。"""
    try:
        db = get_mongo_db()
        task_result = await db.analysis_tasks.delete_one({"task_id": task_id})
        report_result = await db.analysis_reports.delete_many(_build_report_query(task_id))

        if task_result.deleted_count == 0 and report_result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="任务不存在")

        return {
            "success": True,
            "data": {
                "task_deleted": task_result.deleted_count,
                "report_deleted": report_result.deleted_count,
            },
            "message": "任务已删除",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("删除任务失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{analysis_id}", response_model=Dict[str, Any])
async def delete_analysis(analysis_id: str, user: dict = Depends(get_current_user)):
    """兼容旧前端：按 analysis_id/task_id 删除分析。"""
    return await delete_task(analysis_id, user)


@router.get("/{analysis_id}/progress", response_model=Dict[str, Any])
async def get_analysis_progress(analysis_id: str, user: dict = Depends(get_current_user)):
    """兼容旧前端：进度查询映射到任务状态。"""
    return await get_task_status(analysis_id, user)


@router.get("/{analysis_id}/result", response_model=Dict[str, Any])
async def get_analysis_result(analysis_id: str, user: dict = Depends(get_current_user)):
    """兼容旧前端：结果查询映射到任务结果。"""
    return await get_task_result(analysis_id, user)


@router.get("/stock-info", response_model=Dict[str, Any])
async def get_stock_info(
    symbol: str = Query(..., description="6位A股代码"),
    user: dict = Depends(get_current_user),
):
    """查询 A股基础信息。"""
    symbol = _normalize_symbol(symbol)
    _ensure_a_stock(symbol)

    try:
        db = get_mongo_db()
        doc = await db.stock_basic_info.find_one({"$or": [{"symbol": symbol}, {"code": symbol}]})
        data = {
            "symbol": symbol,
            "name": doc.get("name", symbol) if doc else symbol,
            "market": "A股",
            "current_price": 0,
            "change": 0,
            "change_percent": 0,
            "volume": 0,
        }
        return {"success": True, "data": _jsonable(data), "message": "股票信息获取成功"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("获取股票信息失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/search", response_model=Dict[str, Any])
async def search_stocks(
    query: str = Query(..., min_length=1),
    user: dict = Depends(get_current_user),
):
    """A股股票搜索。"""
    try:
        db = get_mongo_db()
        conditions: List[Dict[str, Any]] = [{"name": {"$regex": query, "$options": "i"}}]
        if query.isdigit():
            conditions.extend([{"symbol": {"$regex": query}}, {"code": {"$regex": query}}])

        cursor = db.stock_basic_info.find({"$or": conditions}).limit(10)
        stocks = []
        async for doc in cursor:
            symbol = doc.get("symbol") or doc.get("code")
            if symbol and A_STOCK_PATTERN.fullmatch(str(symbol)):
                stocks.append({
                    "symbol": symbol,
                    "name": doc.get("name", symbol),
                    "market": "A股",
                    "type": "stock",
                })

        return {"success": True, "data": _jsonable(stocks), "message": "股票搜索成功"}
    except Exception as exc:
        logger.error("搜索股票失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.websocket("/ws/task/{task_id}")
async def websocket_task_progress(websocket: WebSocket, task_id: str):
    """WebSocket 推送分析进度。"""
    manager = get_websocket_manager()
    await manager.connect(websocket, task_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket, task_id)
    except Exception as exc:
        logger.error("WebSocket 连接异常: %s - %s", task_id, exc)
        await manager.disconnect(websocket, task_id)
