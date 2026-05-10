"""
A股股票数据 API。

精简版只暴露 A股 6 位数字代码的行情、基础面、K线、新闻和搜索接口。
"""

from __future__ import annotations

from datetime import datetime
import logging
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import get_mongo_db
from app.core.response import ok
from app.routers.auth_db import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stocks", tags=["stocks"])


def _normalize_a_stock_code(code: str) -> str:
    normalized = str(code or "").strip()
    if not re.fullmatch(r"\d{6}", normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="精简版仅支持 6 位数字 A股代码",
        )
    return normalized


def _jsonable_doc(doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not doc:
        return {}
    result = dict(doc)
    result.pop("_id", None)
    for key, value in list(result.items()):
        if isinstance(value, datetime):
            result[key] = value.isoformat()
    return result


async def _get_best_basic_info(db, code: str, source: Optional[str] = None) -> Dict[str, Any]:
    if source:
        doc = await db.stock_basic_info.find_one({"code": code, "source": source})
        return _jsonable_doc(doc)

    enabled_sources = ["tushare", "akshare", "baostock"]
    try:
        from app.core.unified_config import UnifiedConfigManager

        config = UnifiedConfigManager()
        data_source_configs = await config.get_data_source_configs_async()
        configured_sources = [
            ds.type.lower()
            for ds in data_source_configs
            if ds.enabled and ds.type.lower() in enabled_sources
        ]
        if configured_sources:
            enabled_sources = configured_sources
    except Exception as exc:
        logger.debug("读取数据源优先级失败，使用默认顺序: %s", exc)

    for data_source in enabled_sources:
        doc = await db.stock_basic_info.find_one({"code": code, "source": data_source})
        if doc:
            return _jsonable_doc(doc)

    doc = await db.stock_basic_info.find_one({"$or": [{"code": code}, {"symbol": code}]})
    return _jsonable_doc(doc)


@router.get("/{code}/quote", response_model=dict)
async def get_quote(
    code: str,
    force_refresh: bool = Query(False, description="保留参数；A股行情优先读取本地库"),
    current_user: dict = Depends(get_current_user),
):
    """获取 A股实时行情。"""
    code6 = _normalize_a_stock_code(code)
    db = get_mongo_db()

    quote = _jsonable_doc(await db.market_quotes.find_one({"code": code6}))
    basic = await _get_best_basic_info(db, code6)

    if not quote and not basic:
        raise HTTPException(status_code=404, detail="未找到该A股数据")

    data = {
        "code": code6,
        "name": basic.get("name", code6),
        "market": "A股",
        "price": quote.get("close") or quote.get("price"),
        "close": quote.get("close"),
        "open": quote.get("open"),
        "high": quote.get("high"),
        "low": quote.get("low"),
        "prev_close": quote.get("pre_close"),
        "change_percent": quote.get("pct_chg") or quote.get("change_percent"),
        "amount": quote.get("amount"),
        "volume": quote.get("volume"),
        "turnover_rate": quote.get("turnover_rate"),
        "trade_date": quote.get("trade_date"),
        "updated_at": quote.get("updated_at") or basic.get("updated_at"),
        "source": quote.get("source") or basic.get("source"),
    }
    return ok(data=data)


@router.get("/{code}/basic", response_model=dict)
async def get_basic(
    code: str,
    source: Optional[str] = Query(None, description="数据源：tushare/akshare/baostock"),
    force_refresh: bool = Query(False, description="保留参数；A股基础信息优先读取本地库"),
    current_user: dict = Depends(get_current_user),
):
    """获取 A股基础面快照。"""
    code6 = _normalize_a_stock_code(code)
    db = get_mongo_db()
    basic = await _get_best_basic_info(db, code6, source)
    if not basic:
        raise HTTPException(status_code=404, detail="未找到该A股基础信息")

    financial = _jsonable_doc(
        await db.stock_financial_data.find_one(
            {"code": code6},
            sort=[("report_period", -1)],
        )
    )

    data = {
        **basic,
        "code": code6,
        "market": "A股",
        "financial": financial,
    }
    return ok(data=data)


@router.get("/{code}/kline", response_model=dict)
async def get_kline(
    code: str,
    period: str = Query("day", description="day/week/month/5m/15m/30m/60m"),
    limit: int = Query(120, ge=1, le=1000),
    adj: str = Query("none"),
    force_refresh: bool = Query(False, description="保留参数；A股K线优先读取本地库"),
    current_user: dict = Depends(get_current_user),
):
    """获取 A股 K线数据。"""
    code6 = _normalize_a_stock_code(code)
    valid_periods = {"day", "week", "month", "5m", "15m", "30m", "60m"}
    if period not in valid_periods:
        raise HTTPException(status_code=400, detail=f"不支持的period: {period}")

    db = get_mongo_db()
    period_map = {
        "day": "daily",
        "week": "weekly",
        "month": "monthly",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "60m": "60min",
    }
    query: Dict[str, Any] = {"code": code6}
    mapped_period = period_map[period]
    if mapped_period:
        query["period"] = mapped_period
    if adj not in ("none", "", "null", None):
        query["adj"] = adj

    cursor = db.stock_kline.find(query, {"_id": 0}).sort("trade_date", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    if not items:
        cursor = db.stock_daily_quotes.find({"code": code6}, {"_id": 0}).sort("trade_date", -1).limit(limit)
        items = await cursor.to_list(length=limit)

    items = list(reversed(items))
    return ok(data={"code": code6, "period": period, "items": items, "source": "mongodb"})


@router.get("/{code}/news", response_model=dict)
async def get_news(
    code: str,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    include_announcements: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """获取 A股新闻与公告。"""
    code6 = _normalize_a_stock_code(code)

    try:
        from app.services.news_data_service import NewsQueryParams, get_news_data_service
        from app.worker.akshare_sync_service import get_akshare_sync_service

        service = await get_news_data_service()
        params = NewsQueryParams(
            symbol=code6,
            limit=limit,
            sort_by="publish_time",
            sort_order=-1,
        )
        news_list = await service.query_news(params)

        if not news_list:
            sync_service = await get_akshare_sync_service()
            await sync_service.sync_news_data(
                symbols=[code6],
                max_news_per_stock=limit,
                force_update=False,
            )
            news_list = await service.query_news(params)

        items = []
        for news in news_list:
            publish_time = news.get("publish_time", "")
            if isinstance(publish_time, datetime):
                publish_time = publish_time.isoformat()
            items.append({
                "title": news.get("title", ""),
                "source": news.get("source", ""),
                "time": publish_time,
                "url": news.get("url", ""),
                "type": "news",
                "content": news.get("content", ""),
                "summary": news.get("summary", ""),
            })

        return ok(data={"code": code6, "days": days, "limit": limit, "source": "mongodb", "items": items})
    except Exception as exc:
        logger.error("获取A股新闻失败: %s - %s", code6, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取新闻失败: {exc}")


@router.get("/{code}/announcements", response_model=dict)
async def get_announcements(
    code: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """获取 A股公告。"""
    code6 = _normalize_a_stock_code(code)
    db = get_mongo_db()
    cursor = db.stock_announcements.find({"symbol": code6}, {"_id": 0}).sort("publish_time", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    return ok(data={"code": code6, "items": items})


@router.get("/search", response_model=dict)
async def search_stocks(
    q: str = Query(..., min_length=1, description="股票代码或名称"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """搜索 A股股票。"""
    db = get_mongo_db()
    conditions = [{"name": {"$regex": q, "$options": "i"}}]
    if q.isdigit():
        conditions.extend([{"code": {"$regex": q}}, {"symbol": {"$regex": q}}])

    cursor = db.stock_basic_info.find({"$or": conditions}, {"_id": 0}).limit(limit)
    results = []
    async for doc in cursor:
        code = doc.get("code") or doc.get("symbol")
        if code and re.fullmatch(r"\d{6}", str(code)):
            results.append({
                "code": code,
                "symbol": code,
                "name": doc.get("name", code),
                "market": "A股",
                "source": doc.get("source"),
            })

    return ok(data=results)
