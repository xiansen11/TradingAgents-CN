"""China A-share provider backed by optional MCP servers."""

from __future__ import annotations

from datetime import date
import json
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from tradingagents.dataflows.mcp import MCPCallResult, get_mcp_data_gateway
from tradingagents.dataflows.providers.base_provider import BaseStockDataProvider


class ChinaMCPProvider(BaseStockDataProvider):
    def __init__(self) -> None:
        super().__init__("mcp_china")
        self.gateway = get_mcp_data_gateway()

    async def connect(self) -> bool:
        self.connected = self.gateway.is_available()
        return self.connected

    def is_available(self) -> bool:
        return self.gateway.is_available()

    async def get_stock_basic_info(self, symbol: str = None) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        result = await self.gateway.call_async("stock_basic", symbol=symbol)
        if not result.ok:
            history_result = await self.gateway.call_async(
                "market_history",
                symbol=symbol,
                params={"period": "daily"},
            )
            if not history_result.ok:
                return None
            return self.standardize_basic_info(_fallback_basic_info(symbol, history_result))
        data = _first_record(result.content)
        if not data:
            return self.standardize_basic_info(_fallback_basic_info(symbol, result))
        return self.standardize_basic_info(_rename_common_fields(data, symbol))

    async def get_stock_quotes(self, symbol: str) -> Optional[Dict[str, Any]]:
        result = await self.gateway.call_async("market_realtime", symbol=symbol)
        if not result.ok:
            return None
        data = _first_record(result.content)
        if not data:
            return None
        return self.standardize_quotes(_rename_common_fields(data, symbol))

    async def get_historical_data(
        self,
        symbol: str,
        start_date: Union[str, date],
        end_date: Union[str, date] = None,
    ) -> Optional[pd.DataFrame]:
        result = await self.gateway.call_async(
            "market_history",
            symbol=symbol,
            params={"start_date": _date_to_str(start_date), "end_date": _date_to_str(end_date), "period": "daily"},
        )
        return self.historical_result_to_dataframe(result, symbol)

    async def get_financial_data(self, symbol: str, report_type: str = "annual") -> Optional[Dict[str, Any]]:
        result = await self.gateway.call_async("fundamentals", symbol=symbol, params={"report_type": report_type})
        if not result.ok:
            return None
        content = result.content
        if isinstance(content, dict):
            return {"source": result.server, "tool": result.tool, **content}
        return {"source": result.server, "tool": result.tool, "data": content}

    def get_market_report(self, symbol: str, start_date: str, end_date: str, period: str = "daily") -> Optional[str]:
        result = self.gateway.call(
            "market_history",
            symbol=symbol,
            params={"start_date": start_date, "end_date": end_date, "period": period},
        )
        resource_report = _format_stock_mcp_resource_report(symbol, result)
        if resource_report:
            return resource_report
        df = self.historical_result_to_dataframe(result, symbol)
        if df is None or df.empty:
            return None
        stock_name = symbol
        return _format_market_dataframe(df, symbol, stock_name, result)

    def get_fundamentals_report(self, symbol: str) -> Optional[str]:
        result = self.gateway.call("fundamentals", symbol=symbol)
        if not result.ok:
            return None
        return _format_generic_result(f"{symbol} MCP fundamentals", result)

    def get_news_report(self, symbol: str, limit: int = 10) -> Optional[str]:
        result = self.gateway.call("news", symbol=symbol, params={"limit": limit})
        if not result.ok:
            return None
        return _format_generic_result(f"{symbol} MCP news", result)

    def get_sentiment_report(self, symbol: str) -> Optional[str]:
        result = self.gateway.call("sentiment", symbol=symbol)
        if not result.ok:
            return None
        return _format_generic_result(f"{symbol} MCP sentiment", result)

    def historical_result_to_dataframe(self, result: MCPCallResult, symbol: str) -> Optional[pd.DataFrame]:
        if not result.ok:
            return None

        records = _records_from_content(result.content)
        if not records:
            records = _records_from_stock_mcp_resource_response(result.content, symbol)
        if not records:
            return None

        normalized = [_rename_common_fields(record, symbol) for record in records]
        df = pd.DataFrame(normalized)
        if df.empty:
            return None

        rename_map = {
            "trade_date": "date",
            "datetime": "date",
            "current_price": "close",
            "volume": "vol",
            "pct_chg": "pct_change",
        }
        df = df.rename(columns={key: value for key, value in rename_map.items() if key in df.columns})
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.sort_values("date")
        return df


def _date_to_str(value: Union[str, date, None]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _records_from_content(content: Any) -> List[Dict[str, Any]]:
    if isinstance(content, dict):
        if _has_stock_mcp_resources(content):
            return []
        for key in ("data", "items", "records", "result", "rows"):
            value = content.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [content]
    if isinstance(content, list):
        records: List[Dict[str, Any]] = []
        for item in content:
            if isinstance(item, dict):
                records.extend(_records_from_content(item))
        return records
    return []


def _has_stock_mcp_resources(content: Dict[str, Any]) -> bool:
    structured_content = content.get("structuredContent")
    if not isinstance(structured_content, dict):
        return False
    resources = structured_content.get("resources")
    return isinstance(resources, list) and bool(resources)


def _format_stock_mcp_resource_report(symbol: str, result: MCPCallResult) -> Optional[str]:
    if not result.ok or not isinstance(result.content, dict) or not _has_stock_mcp_resources(result.content):
        return None

    structured_content = result.content.get("structuredContent") or {}
    resources = structured_content.get("resources") or []
    resource = resources[0] if resources else {}
    text = ""
    for item in result.content.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            text = str(item.get("text") or "")
            break

    record_count = _extract_record_count(text) or 1
    resource_name = resource.get("name") or f"{symbol} K线数据"
    description = resource.get("description") or text or "stock-mcp returned market data"
    resource_path = resource.get("workspacePath") or resource.get("uri") or ""

    return (
        f"# {symbol} market data (MCP)\n\n"
        f"Stock: {symbol}\n"
        f"Data source: {result.server}.{result.tool}\n"
        f"Latency: {result.latency_ms:.0f} ms\n"
        f"Rows: {record_count}\n"
        f"Fields: date, open, high, low, close, volume\n"
        f"Resource: {resource_name}\n"
        f"Path: {resource_path}\n\n"
        f"{description}"
    )


def _records_from_stock_mcp_resource_response(content: Any, symbol: str) -> List[Dict[str, Any]]:
    if not isinstance(content, dict):
        return []
    structured_content = content.get("structuredContent")
    if not isinstance(structured_content, dict):
        return []
    resources = structured_content.get("resources")
    if not isinstance(resources, list) or not resources:
        return []

    text = ""
    for item in content.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            text = str(item.get("text") or "")
            break

    record_count = _extract_record_count(text) or 1
    return [
        {
            "symbol": symbol,
            "date": pd.Timestamp.today().normalize(),
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
            "vol": 0.0,
            "amount": 0.0,
            "source": "stock-mcp",
            "record_count": record_count,
            "resource": resources[0],
        }
    ]


def _extract_record_count(text: str) -> Optional[int]:
    import re

    match = re.search(r"共\s*(\d+)\s*条", text)
    if match:
        return int(match.group(1))
    return None


def _first_record(content: Any) -> Optional[Dict[str, Any]]:
    records = _records_from_content(content)
    return records[0] if records else None


def _fallback_basic_info(symbol: str, result: MCPCallResult) -> Dict[str, Any]:
    code = str(symbol or "").strip()
    display_code = code.split(".", 1)[0]
    return {
        "symbol": code,
        "code": code,
        "name": f"A股{display_code}",
        "market": _infer_market(code),
        "industry": "未知",
        "area": "未知",
        "source": f"{result.server}.{result.tool}",
    }


def _infer_market(symbol: str) -> str:
    code = str(symbol or "").strip()
    if code.startswith(("6", "5", "9")):
        return "上海证券交易所"
    if code.startswith(("0", "2", "3")):
        return "深圳证券交易所"
    if code.startswith(("4", "8")):
        return "北京证券交易所"
    return "A股"


def _rename_common_fields(record: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    aliases = {
        "\u4ee3\u7801": "symbol",
        "\u80a1\u7968\u4ee3\u7801": "symbol",
        "\u8bc1\u5238\u4ee3\u7801": "symbol",
        "\u540d\u79f0": "name",
        "\u7b80\u79f0": "name",
        "\u80a1\u7968\u7b80\u79f0": "name",
        "\u65e5\u671f": "trade_date",
        "\u65f6\u95f4": "trade_date",
        "\u4ea4\u6613\u65e5\u671f": "trade_date",
        "\u5f00\u76d8": "open",
        "\u4eca\u5f00": "open",
        "\u6700\u9ad8": "high",
        "\u6700\u4f4e": "low",
        "\u6536\u76d8": "close",
        "\u6700\u65b0": "current_price",
        "\u6700\u65b0\u4ef7": "current_price",
        "\u6210\u4ea4\u91cf": "volume",
        "\u6210\u4ea4\u989d": "amount",
        "\u6da8\u8dcc\u5e45": "pct_chg",
        "\u6da8\u8dcc\u989d": "change",
    }
    normalized = {aliases.get(key, key): value for key, value in record.items()}
    normalized.setdefault("symbol", symbol)
    normalized.setdefault("code", symbol)
    return normalized


def _format_market_dataframe(df: pd.DataFrame, symbol: str, stock_name: str, result: MCPCallResult) -> str:
    preview_cols = [col for col in ["date", "open", "high", "low", "close", "vol", "amount", "pct_change"] if col in df.columns]
    preview = df[preview_cols].tail(20).to_string(index=False) if preview_cols else df.tail(20).to_string(index=False)
    return (
        f"# {symbol} market data (MCP)\n\n"
        f"Stock: {stock_name}\n"
        f"Data source: {result.server}.{result.tool}\n"
        f"Latency: {result.latency_ms:.0f} ms\n"
        f"Rows: {len(df)}\n\n"
        f"{preview}"
    )


def _format_generic_result(title: str, result: MCPCallResult) -> str:
    content = result.content
    if isinstance(content, (dict, list)):
        body = json.dumps(content, ensure_ascii=False, indent=2, default=str)
    else:
        body = str(content)
    return (
        f"# {title}\n\n"
        f"Data source: {result.server}.{result.tool}\n"
        f"Latency: {result.latency_ms:.0f} ms\n\n"
        f"{body}"
    )


_china_mcp_provider: Optional[ChinaMCPProvider] = None


def get_china_mcp_provider() -> ChinaMCPProvider:
    global _china_mcp_provider
    if _china_mcp_provider is None:
        _china_mcp_provider = ChinaMCPProvider()
    return _china_mcp_provider
