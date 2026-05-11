"""External tool and data source diagnostics."""

from __future__ import annotations

import asyncio
import math
import re
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db
from app.core.response import ok
from app.routers.auth_db import get_current_user

router = APIRouter(prefix="/tool-tests", tags=["tool-tests"])


DEFAULT_MODULES = ["quote", "technical", "fundamentals", "news", "mcp"]
MCP_CAPABILITIES = [
    "market_realtime",
    "market_history",
    "stock_basic",
    "fundamentals",
    "news",
    "sentiment",
]
NON_ERROR_STATUSES = {"success", "unsupported", "skipped"}


def _market_prefixed_code(code: str) -> str:
    if code.startswith(("60", "68", "90")):
        return f"sh{code}"
    if code.startswith(("8", "4", "9")):
        return f"bj{code}"
    return f"sz{code}"


def _baostock_code(code: str) -> str:
    if code.startswith(("60", "68", "90")):
        return f"sh.{code}"
    return f"sz.{code}"


class ToolTestRequest(BaseModel):
    code: str = Field(..., description="A-share 6 digit stock code")
    include_raw: bool = False
    timeout_seconds: float = Field(default=20, ge=1, le=120)
    modules: List[str] = Field(default_factory=lambda: list(DEFAULT_MODULES))


def _normalize_a_stock_code(code: str) -> str:
    normalized = str(code or "").strip()
    if not re.fullmatch(r"\d{6}", normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="首版工具测试仅支持 6 位数字 A 股代码",
        )
    return normalized


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, pd.DataFrame):
        return [_jsonable(row) for row in value.head(20).to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return _jsonable(value.to_dict())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items() if key != "_id"}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in list(value)[:50]]
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _sample(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return {
            "rows": int(len(value)),
            "columns": list(value.columns[:12]),
            "preview": _jsonable(value.head(3)),
        }
    if isinstance(value, dict):
        keys = list(value.keys())
        return {key: _jsonable(value[key]) for key in keys[:8]}
    if isinstance(value, list):
        return {
            "count": len(value),
            "preview": _jsonable(value[:3]),
        }
    text = str(value)
    return text if len(text) <= 500 else text[:500] + "..."


def _make_diagnostic(
    source: str,
    module: str,
    status_value: str,
    latency_ms: float,
    message: str,
    result: Any = None,
    include_raw: bool = False,
) -> Dict[str, Any]:
    return {
        "source": source,
        "module": module,
        "status": status_value,
        "latency_ms": round(latency_ms, 2),
        "message": message,
        "sample": _sample(result) if result is not None else None,
        "raw": _jsonable(result) if include_raw and result is not None else None,
    }


def _is_meaningful_result(result: Any) -> bool:
    if hasattr(result, "ok"):
        return bool(getattr(result, "ok"))
    if isinstance(result, bool):
        return result
    if isinstance(result, pd.DataFrame):
        return not result.empty
    if isinstance(result, (list, tuple, dict, set)):
        return bool(result)
    return result is not None


async def _timed_call(
    source: str,
    module: str,
    func,
    include_raw: bool,
    timeout_seconds: float,
    empty_status: str = "error",
    empty_message: str = "未返回有效数据",
    success_message: str = "获取成功",
) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(asyncio.to_thread(func), timeout=timeout_seconds)
        latency_ms = (time.perf_counter() - start) * 1000
        ok_result = _is_meaningful_result(result)
        status_value = "success" if ok_result else "error"
        result_error = getattr(result, "error", None)
        if not ok_result and not result_error:
            status_value = empty_status
        message = success_message if ok_result else (str(result_error) if result_error else empty_message)
        return _make_diagnostic(source, module, status_value, latency_ms, message, result, include_raw)
    except asyncio.TimeoutError:
        latency_ms = (time.perf_counter() - start) * 1000
        return _make_diagnostic(source, module, "error", latency_ms, f"调用超时（>{timeout_seconds}s）")
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return _make_diagnostic(source, module, "error", latency_ms, str(exc))


async def _get_best_basic_info(db, code: str) -> Dict[str, Any]:
    for source in ["tushare", "akshare", "baostock"]:
        doc = await db.stock_basic_info.find_one({"code": code, "source": source})
        if doc:
            return _jsonable(doc)
    doc = await db.stock_basic_info.find_one({"$or": [{"code": code}, {"symbol": code}]})
    return _jsonable(doc or {})


async def _run_local_mongo_tests(code: str, include_raw: bool, modules: set[str]) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    diagnostics: List[Dict[str, Any]] = []
    snapshot: Dict[str, Any] = {"quote": None, "technical": None, "fundamentals": None, "news": None}
    db = get_mongo_db()

    if "quote" in modules:
        start = time.perf_counter()
        quote = _jsonable(await db.market_quotes.find_one({"code": code})) or {}
        basic = await _get_best_basic_info(db, code) or {}
        data = {
            "code": code,
            "name": basic.get("name", code),
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
        snapshot["quote"] = data if quote or basic else None
        diagnostics.append(_make_diagnostic(
            "mongodb",
            "quote",
            "success" if quote or basic else "error",
            (time.perf_counter() - start) * 1000,
            "本地行情读取成功" if quote or basic else "本地库未找到行情或基础信息",
            data if quote or basic else None,
            include_raw,
        ))

    if "fundamentals" in modules:
        start = time.perf_counter()
        basic = await _get_best_basic_info(db, code)
        financial = _jsonable(
            await db.stock_financial_data.find_one({"code": code}, sort=[("report_period", -1)])
        )
        fundamentals = {**basic, "code": code, "market": "A股", "financial": financial}
        snapshot["fundamentals"] = fundamentals if basic else None
        diagnostics.append(_make_diagnostic(
            "mongodb",
            "fundamentals",
            "success" if basic else "error",
            (time.perf_counter() - start) * 1000,
            "本地基本面读取成功" if basic else "本地库未找到基础信息",
            fundamentals if basic else None,
            include_raw,
        ))

    if "technical" in modules:
        start = time.perf_counter()
        cursor = db.stock_kline.find({"code": code}, {"_id": 0}).sort("trade_date", -1).limit(120)
        items = await cursor.to_list(length=120)
        if not items:
            cursor = db.stock_daily_quotes.find({"code": code}, {"_id": 0}).sort("trade_date", -1).limit(120)
            items = await cursor.to_list(length=120)
        items = list(reversed(_jsonable(items)))
        technical = _build_technical_summary(items)
        snapshot["technical"] = technical
        diagnostics.append(_make_diagnostic(
            "mongodb",
            "technical",
            "success" if technical.get("indicators") else "error",
            (time.perf_counter() - start) * 1000,
            technical.get("message", "技术指标计算完成"),
            {"kline_count": len(items), **technical},
            include_raw,
        ))

    if "news" in modules:
        start = time.perf_counter()
        news_items: List[Dict[str, Any]] = []
        try:
            from app.services.news_data_service import NewsQueryParams, get_news_data_service

            service = await get_news_data_service()
            params = NewsQueryParams(symbol=code, limit=20, sort_by="publish_time", sort_order=-1)
            news_items = _jsonable(await service.query_news(params))
        except Exception as exc:
            diagnostics.append(_make_diagnostic(
                "news_service",
                "news",
                "error",
                (time.perf_counter() - start) * 1000,
                str(exc),
            ))
        else:
            snapshot["news"] = {
                "count": len(news_items),
                "items": [
                    {
                        "title": item.get("title", ""),
                        "source": item.get("source", ""),
                        "time": item.get("publish_time") or item.get("time", ""),
                        "url": item.get("url", ""),
                    }
                    for item in news_items[:10]
                ],
            }
            diagnostics.append(_make_diagnostic(
                "news_service",
                "news",
                "success" if news_items else "error",
                (time.perf_counter() - start) * 1000,
                "新闻服务读取成功" if news_items else "新闻服务未返回数据",
                news_items,
                include_raw,
            ))

    return snapshot, diagnostics


def _build_technical_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return {"message": "没有可用于技术指标计算的 K 线数据", "indicators": None}
    try:
        from tradingagents.tools.analysis.indicators import add_all_indicators

        rows = []
        for item in items:
            rows.append({
                "time": item.get("time") or item.get("trade_date") or item.get("date"),
                "open": item.get("open"),
                "high": item.get("high"),
                "low": item.get("low"),
                "close": item.get("close") or item.get("price"),
                "volume": item.get("volume"),
                "amount": item.get("amount"),
            })
        df = pd.DataFrame(rows)
        for column in ["open", "high", "low", "close", "volume", "amount"]:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")
        df = df.dropna(subset=["close"])
        if df.empty:
            return {"message": "K 线数据缺少有效收盘价", "indicators": None}
        df = add_all_indicators(df, close_col="close", high_col="high", low_col="low", rsi_style="china")
        latest = _jsonable(df.iloc[-1].to_dict())
        keys = [
            "close",
            "ma5",
            "ma10",
            "ma20",
            "ma60",
            "macd_dif",
            "macd_dea",
            "macd",
            "rsi6",
            "rsi12",
            "rsi24",
            "rsi14",
            "boll_mid",
            "boll_upper",
            "boll_lower",
        ]
        return {
            "message": "技术指标计算完成",
            "bars": int(len(df)),
            "latest_time": latest.get("time"),
            "indicators": {key: latest.get(key) for key in keys},
        }
    except Exception as exc:
        return {"message": f"技术指标计算失败: {exc}", "indicators": None}


async def _run_mcp_tests(code: str, include_raw: bool, timeout_seconds: float) -> List[Dict[str, Any]]:
    diagnostics: List[Dict[str, Any]] = []
    try:
        from tradingagents.dataflows.mcp.gateway import get_mcp_data_gateway
    except Exception as exc:
        return [_make_diagnostic("mcp", "gateway", "error", 0, f"MCP 网关不可用: {exc}")]

    gateway = get_mcp_data_gateway()
    configured_servers = gateway.list_configured_servers()
    if not gateway.is_available():
        diagnostics.append(_make_diagnostic(
            "mcp",
            "availability",
            "error",
            0,
            "MCP 未启用、未配置服务器或 mcp 包不可用",
            {"configured_servers": list(configured_servers.keys())},
            include_raw,
        ))

    for server in configured_servers:
        diagnostics.append(await _timed_call(
            server,
            "tools/list",
            lambda server_name=server: gateway.list_tools(server_name),
            include_raw,
            timeout_seconds,
        ))

    for capability in MCP_CAPABILITIES:
        diagnostics.append(await _timed_call(
            "mcp",
            capability,
            lambda cap=capability: gateway.call(cap, code, {"limit": 10, "period": "day"}),
            include_raw,
            timeout_seconds,
        ))

    if not configured_servers:
        diagnostics.append(_make_diagnostic("mcp", "servers", "error", 0, "没有配置 MCP 服务器"))
    return diagnostics


async def _run_adapter_tests(
    code: str,
    include_raw: bool,
    timeout_seconds: float,
    modules: set[str],
) -> List[Dict[str, Any]]:
    try:
        from app.services.data_sources.manager import DataSourceManager
    except Exception as exc:
        return [_make_diagnostic("data_sources", "manager", "error", 0, f"数据源管理器不可用: {exc}")]

    try:
        manager = await asyncio.to_thread(DataSourceManager)
        adapters = manager.adapters
    except Exception as exc:
        return [_make_diagnostic("data_sources", "manager", "error", 0, str(exc))]

    diagnostics: List[Dict[str, Any]] = []
    for adapter in adapters:
        source = getattr(adapter, "name", adapter.__class__.__name__)
        availability = await _timed_call(
            source,
            "availability",
            adapter.is_available,
            include_raw,
            timeout_seconds,
            empty_status="error",
            empty_message=_adapter_unavailable_message(adapter),
        )
        diagnostics.append(availability)
        if availability["status"] != "success":
            for module in sorted(modules):
                diagnostics.append(_make_diagnostic(
                    source,
                    _adapter_module_name(module),
                    "skipped",
                    0,
                    "数据源不可用，已跳过该能力测试",
                ))
            continue

        if "quote" in modules:
            diagnostics.append(await _run_adapter_quote_test(adapter, code, include_raw, timeout_seconds))
        if "technical" in modules:
            diagnostics.append(await _run_adapter_kline_test(adapter, code, include_raw, timeout_seconds))
        if "fundamentals" in modules:
            diagnostics.append(await _run_adapter_fundamentals_test(adapter, code, include_raw, timeout_seconds))
        if "news" in modules:
            diagnostics.append(await _run_adapter_news_test(adapter, code, include_raw, timeout_seconds))
    return diagnostics


def _adapter_module_name(module: str) -> str:
    return "kline" if module == "technical" else module


def _adapter_unavailable_message(adapter: Any) -> str:
    source = getattr(adapter, "name", adapter.__class__.__name__)
    if source == "tushare":
        token_source = getattr(adapter, "get_token_source", lambda: None)()
        token_message = f"（Token 来源: {token_source}）" if token_source else ""
        return f"Tushare 不可用，请检查 Token 是否正确或已配置 TUSHARE_TOKEN {token_message}".strip()
    return f"{source} 不可用，请检查依赖安装、网络或数据源配置"


async def _run_adapter_quote_test(
    adapter: Any,
    code: str,
    include_raw: bool,
    timeout_seconds: float,
) -> Dict[str, Any]:
    source = getattr(adapter, "name", adapter.__class__.__name__)
    if source == "baostock":
        return _make_diagnostic(source, "quote", "unsupported", 0, "当前 BaoStock 适配器未实现实时行情能力")
    return await _timed_call(
        source,
        "quote",
        lambda: _adapter_quote_call(adapter, code),
        include_raw,
        timeout_seconds,
        empty_message=f"{source} 行情接口未返回 {code} 的数据；可能是接口限流、网络异常或非交易时段数据缺失",
    )


def _adapter_quote_call(adapter: Any, code: str) -> Any:
    if getattr(adapter, "name", "") == "akshare":
        return _akshare_single_quote(code)
    return (adapter.get_realtime_quotes() or {}).get(code)


def _akshare_single_quote(code: str) -> Optional[Dict[str, Any]]:
    try:
        import akshare as ak

        df = ak.stock_individual_info_em(symbol=_market_prefixed_code(code))
        if df is None or getattr(df, "empty", True):
            df = ak.stock_individual_info_em(symbol=code)
        if df is None or getattr(df, "empty", True):
            return None

        info: Dict[str, Any] = {}
        for _, row in df.iterrows():
            item = row.get("item") or row.get("项目") or row.get("指标")
            if item:
                info[str(item)] = _jsonable(row.get("value") or row.get("值") or row.get("数据"))
        if not info:
            return None
        return {
            "code": code,
            "name": info.get("股票简称") or info.get("简称") or info.get("名称"),
            "close": info.get("最新"),
            "total_market_value": info.get("总市值"),
            "source": "akshare.stock_individual_info_em",
            "info": info,
        }
    except Exception:
        return None


async def _run_adapter_kline_test(
    adapter: Any,
    code: str,
    include_raw: bool,
    timeout_seconds: float,
) -> Dict[str, Any]:
    source = getattr(adapter, "name", adapter.__class__.__name__)
    if source == "baostock":
        return _make_diagnostic(source, "kline", "unsupported", 0, "当前 BaoStock 适配器未实现 K 线能力")
    return await _timed_call(
        source,
        "kline",
        lambda: adapter.get_kline(code=code, period="day", limit=120, adj=None),
        include_raw,
        timeout_seconds,
        empty_message=f"{source} K 线接口未返回 {code} 的日线数据",
    )


async def _run_adapter_fundamentals_test(
    adapter: Any,
    code: str,
    include_raw: bool,
    timeout_seconds: float,
) -> Dict[str, Any]:
    source = getattr(adapter, "name", adapter.__class__.__name__)
    if source == "baostock":
        return await _timed_call(
            source,
            "fundamentals",
            lambda: _baostock_single_fundamentals(code),
            include_raw,
            min(timeout_seconds, 8),
            empty_message="BaoStock 单股估值接口未返回数据，常见原因是非交易日、网络接收异常或接口字段为空",
        )
    if source == "akshare":
        return await _timed_call(
            source,
            "fundamentals",
            lambda: _akshare_single_quote(code),
            include_raw,
            timeout_seconds,
            empty_message="AKShare 单股基本面接口未返回数据",
            success_message="单股基本面读取成功",
        )

    def _basic_call():
        trade_date = adapter.find_latest_trade_date()
        df = adapter.get_daily_basic(trade_date) if trade_date else None
        return _match_dataframe_code(df, code)

    return await _timed_call(
        source,
        "fundamentals",
        _basic_call,
        include_raw,
        timeout_seconds,
        empty_message=f"{source} 基本面接口未返回 {code} 的数据",
    )


def _baostock_single_fundamentals(code: str) -> Optional[Dict[str, Any]]:
    try:
        import baostock as bs

        login = bs.login()
        if login.error_code != "0":
            return None
        try:
            end_date = datetime.now().strftime("%Y-%m-%d")
            rs = bs.query_history_k_data_plus(
                _baostock_code(code),
                "date,code,close,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST",
                end_date=end_date,
                frequency="d",
                adjustflag="3",
            )
            if rs.error_code != "0":
                return None
            rows = []
            while (rs.error_code == "0") & rs.next():
                rows.append(dict(zip(rs.fields, rs.get_row_data())))
            return rows[-1] if rows else None
        finally:
            bs.logout()
    except Exception:
        return None


async def _run_adapter_news_test(
    adapter: Any,
    code: str,
    include_raw: bool,
    timeout_seconds: float,
) -> Dict[str, Any]:
    source = getattr(adapter, "name", adapter.__class__.__name__)
    if source == "baostock":
        return _make_diagnostic(source, "news", "unsupported", 0, "当前 BaoStock 适配器未实现新闻能力")
    return await _timed_call(
        source,
        "news",
        lambda: adapter.get_news(code=code, days=7, limit=20, include_announcements=True),
        include_raw,
        timeout_seconds,
        empty_message=f"{source} 新闻接口未返回 {code} 的新闻或公告",
    )


def _match_dataframe_code(df: Any, code: str) -> Any:
    if isinstance(df, pd.DataFrame) and not df.empty:
        code_cols = [col for col in ["code", "symbol", "ts_code"] if col in df.columns]
        for col in code_cols:
            matched = df[df[col].astype(str).str.contains(code, na=False)]
            if not matched.empty:
                return matched.head(5)
    return df


@router.get("/sources", response_model=dict)
async def get_tool_test_sources(current_user: dict = Depends(get_current_user)):
    """Return sources and modules supported by the tool test page."""
    mcp_servers: List[str] = []
    try:
        from tradingagents.dataflows.mcp.gateway import get_mcp_data_gateway

        gateway = get_mcp_data_gateway()
        mcp_servers = list(gateway.list_configured_servers().keys())
    except Exception:
        mcp_servers = []

    return ok(data={
        "market_scope": "A股",
        "modules": list(DEFAULT_MODULES),
        "data_sources": ["mongodb", "news_service", "akshare", "tushare", "baostock"],
        "mcp_servers": mcp_servers,
        "mcp_capabilities": list(MCP_CAPABILITIES),
    })


@router.post("/stock", response_model=dict)
async def test_stock_tools(
    payload: ToolTestRequest,
    current_user: dict = Depends(get_current_user),
):
    """Run snapshot and diagnostics for a single A-share stock code."""
    code = _normalize_a_stock_code(payload.code)
    modules = set(payload.modules or DEFAULT_MODULES)
    start = time.perf_counter()

    snapshot, diagnostics = await _run_local_mongo_tests(code, payload.include_raw, modules)

    if "mcp" in modules:
        diagnostics.extend(await _run_mcp_tests(code, payload.include_raw, payload.timeout_seconds))

    adapter_modules = modules & {"quote", "technical", "fundamentals", "news"}
    if adapter_modules:
        diagnostics.extend(await _run_adapter_tests(code, payload.include_raw, payload.timeout_seconds, adapter_modules))

    success_count = sum(1 for item in diagnostics if item["status"] == "success")
    non_error_count = sum(1 for item in diagnostics if item["status"] in NON_ERROR_STATUSES)
    failure_count = sum(1 for item in diagnostics if item["status"] == "error")
    name = (snapshot.get("quote") or {}).get("name") or (snapshot.get("fundamentals") or {}).get("name") or code
    summary = {
        "code": code,
        "name": name,
        "overall_status": "success" if failure_count == 0 else ("partial" if non_error_count else "error"),
        "success_count": success_count,
        "failure_count": failure_count,
        "skipped_count": sum(1 for item in diagnostics if item["status"] == "skipped"),
        "unsupported_count": sum(1 for item in diagnostics if item["status"] == "unsupported"),
        "total_count": len(diagnostics),
        "total_latency_ms": round((time.perf_counter() - start) * 1000, 2),
    }
    return ok(data={"summary": summary, "snapshot": snapshot, "diagnostics": diagnostics})
