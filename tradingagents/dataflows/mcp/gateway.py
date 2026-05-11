"""MCP gateway used behind the existing unified data tools.

The gateway is intentionally optional. If the ``mcp`` package, an MCP server
command, or an HTTP endpoint is missing, calls fail closed and callers can
continue through the legacy local providers.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


@dataclass
class MCPCallResult:
    server: str
    tool: str
    arguments: Dict[str, Any]
    content: Any = None
    latency_ms: float = 0.0
    error: Optional[str] = None
    cached: bool = False

    @property
    def ok(self) -> bool:
        if self.error is not None or self.content in (None, "", [], {}):
            return False
        if isinstance(self.content, dict):
            if self.content.get("isError") is True:
                return False
            structured_content = self.content.get("structuredContent")
            if isinstance(structured_content, dict) and structured_content.get("error"):
                return False
        return True


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    transport: str
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    url: Optional[str] = None


@dataclass(frozen=True)
class MCPToolRoute:
    server: str
    tool: str
    argument_map: Dict[str, str] = field(default_factory=dict)
    defaults: Dict[str, Any] = field(default_factory=dict)
    transform: Optional[str] = None


class MCPDataGateway:
    """Routes stable project capabilities to whitelisted third-party MCP tools."""

    CAPABILITY_ROUTES: Dict[str, List[MCPToolRoute]] = {
        "market_history": [
            MCPToolRoute(
                "china_stock_mcp",
                "get_kline_data",
                {"symbol": "symbol", "period": "period"},
                {"period": "1y", "interval": "1d"},
                "stock_mcp",
            ),
            MCPToolRoute(
                "china_stock_mcp",
                "get_hist_data",
                {"symbol": "symbol", "start_date": "start_date", "end_date": "end_date", "period": "period"},
                {"period": "daily"},
                "china_stock",
            ),
            MCPToolRoute(
                "china_stock_mcp",
                "get_cni_index_hist",
                {"symbol": "symbol", "start_date": "start_date", "end_date": "end_date"},
                transform="china_stock",
            ),
        ],
        "market_realtime": [
            MCPToolRoute("china_stock_mcp", "get_real_time_price", {"symbol": "symbol"}, transform="stock_mcp"),
            MCPToolRoute("china_stock_mcp", "get_realtime_data", {"symbol": "symbol"}, transform="china_stock"),
        ],
        "stock_basic": [
            MCPToolRoute("china_stock_mcp", "get_asset_info", {"symbol": "symbol"}, transform="stock_mcp"),
            MCPToolRoute("china_stock_mcp", "get_stock_basic_info", {"symbol": "symbol"}, transform="china_stock"),
            MCPToolRoute("china_stock_mcp", "get_stock_a_code_name", {"symbol": "symbol"}, transform="china_stock"),
        ],
        "fundamentals": [
            MCPToolRoute("china_stock_mcp", "get_financial_reports", {"symbol": "symbol"}, transform="stock_mcp"),
            MCPToolRoute("china_stock_mcp", "get_valuation_metrics", {"symbol": "symbol"}, transform="stock_mcp"),
            MCPToolRoute(
                "finance_mcp",
                "company_performance",
                {"symbol": "ts_code", "data_type": "data_type", "start_date": "start_date", "end_date": "end_date"},
                {"data_type": "fina_indicator"},
                "finance",
            ),
            MCPToolRoute("china_stock_mcp", "get_financial_metrics", {"symbol": "symbol"}, transform="china_stock"),
            MCPToolRoute("china_stock_mcp", "get_stock_value", {"symbol": "symbol"}, transform="china_stock"),
            MCPToolRoute("china_stock_mcp", "get_income_statement", {"symbol": "symbol"}, transform="china_stock"),
            MCPToolRoute("china_stock_mcp", "get_balance_sheet", {"symbol": "symbol"}, transform="china_stock"),
            MCPToolRoute("china_stock_mcp", "get_cash_flow", {"symbol": "symbol"}, transform="china_stock"),
            MCPToolRoute("tushare_mcp", "sdk_call", {"symbol": "symbol", "api_name": "api_name"}, {"api_name": "fina_indicator"}),
        ],
        "news": [
            MCPToolRoute("china_stock_mcp", "get_stock_news", {"symbol": "symbol", "limit": "limit"}, transform="stock_mcp"),
            MCPToolRoute("finance_mcp", "finance_news", {"symbol": "query", "limit": "limit"}, transform="finance"),
            MCPToolRoute("finance_mcp", "hot_news_7x24", {"limit": "limit"}),
            MCPToolRoute("china_stock_mcp", "get_news_data", {"symbol": "symbol", "limit": "limit"}, transform="china_stock"),
            MCPToolRoute("china_stock_mcp", "get_stock_research_report", {"symbol": "symbol", "limit": "limit"}, transform="china_stock"),
        ],
        "sentiment": [
            MCPToolRoute("china_stock_mcp", "get_money_flow", {"symbol": "symbol"}, transform="stock_mcp"),
            MCPToolRoute("finance_mcp", "money_flow", {"symbol": "ts_code"}, transform="finance"),
            MCPToolRoute("finance_mcp", "dragon_tiger_inst", {"symbol": "ts_code"}, transform="finance"),
            MCPToolRoute("finance_mcp", "block_trade", {"symbol": "ts_code"}, transform="finance"),
            MCPToolRoute("finance_mcp", "margin_trade", {"symbol": "ts_code"}, transform="finance"),
            MCPToolRoute("china_stock_mcp", "get_fund_flow", {"symbol": "symbol"}, transform="china_stock"),
            MCPToolRoute("china_stock_mcp", "get_investor_sentiment", {"symbol": "symbol"}, transform="china_stock"),
            MCPToolRoute("china_stock_mcp", "get_stock_technical_rank", {"symbol": "symbol"}, transform="china_stock"),
        ],
    }

    def __init__(self) -> None:
        self.enabled = os.getenv("MCP_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
        self.timeout_seconds = float(os.getenv("MCP_TIMEOUT_SECONDS", "30"))
        self._server_configs = self._load_server_configs()
        self._tool_cache: Dict[str, set[str]] = {}

    def is_available(self) -> bool:
        return self.enabled and bool(self._server_configs) and self._mcp_package_available()

    def list_configured_servers(self) -> Dict[str, MCPServerConfig]:
        return dict(self._server_configs)

    def list_tools(self, server: str) -> MCPCallResult:
        config = self._server_configs.get(server)
        if config is None:
            return MCPCallResult(server, "tools/list", {}, error=f"MCP server is not configured: {server}")
        if not self._mcp_package_available():
            return MCPCallResult(server, "tools/list", {}, error="Python package 'mcp' is not installed")

        start = time.perf_counter()
        try:
            tools = _run_async_safely(self._list_tools(config))
            self._tool_cache[server] = tools
            return MCPCallResult(
                server=server,
                tool="tools/list",
                arguments={},
                content=sorted(tools),
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as exc:
            return MCPCallResult(
                server=server,
                tool="tools/list",
                arguments={},
                latency_ms=(time.perf_counter() - start) * 1000,
                error=str(exc),
            )

    def call(self, capability: str, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> MCPCallResult:
        return _run_async_safely(self.call_async(capability, symbol, params))

    async def call_async(
        self,
        capability: str,
        symbol: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> MCPCallResult:
        params = params or {}
        if symbol:
            params = {"symbol": symbol, **params}

        if not self.enabled:
            return MCPCallResult("", "", params, error="MCP is disabled")
        if capability not in self.CAPABILITY_ROUTES:
            return MCPCallResult("", "", params, error=f"Unsupported MCP capability: {capability}")
        if not self._mcp_package_available():
            return MCPCallResult("", "", params, error="Python package 'mcp' is not installed")

        route_errors: List[str] = []
        for route in self.CAPABILITY_ROUTES[capability]:
            server_config = self._server_configs.get(route.server)
            if server_config is None:
                route_errors.append(f"{route.server}.{route.tool}: MCP server is not configured")
                continue

            arguments = self._build_arguments(route, params)
            result = await self._call_route(server_config, route.tool, arguments)
            if result.ok:
                return result
            route_errors.append(
                f"{route.server}.{route.tool}: {result.error or 'returned empty result'}"
            )

        detail = "; ".join(route_errors)
        message = f"No usable MCP route for {capability}"
        if detail:
            message = f"{message}: {detail}"
        return MCPCallResult("", "", params, error=message)

    async def _call_route(self, server_config: MCPServerConfig, tool_name: str, arguments: Dict[str, Any]) -> MCPCallResult:
        start = time.perf_counter()
        try:
            if not await self._tool_is_allowed(server_config, tool_name):
                return MCPCallResult(
                    server_config.name,
                    tool_name,
                    arguments,
                    latency_ms=(time.perf_counter() - start) * 1000,
                    error=f"MCP tool is not exposed by {server_config.name}: {tool_name}",
                )

            if server_config.transport == "stdio":
                content = await self._call_stdio_tool(server_config, tool_name, arguments)
            elif server_config.transport in {"streamable_http", "http"}:
                content = await self._call_http_tool(server_config, tool_name, arguments)
            else:
                raise ValueError(f"Unsupported MCP transport: {server_config.transport}")

            return MCPCallResult(
                server=server_config.name,
                tool=tool_name,
                arguments=arguments,
                content=self._normalize_content(content),
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as exc:
            logger.warning("MCP call failed: server=%s tool=%s error=%s", server_config.name, tool_name, exc)
            return MCPCallResult(
                server=server_config.name,
                tool=tool_name,
                arguments=arguments,
                latency_ms=(time.perf_counter() - start) * 1000,
                error=str(exc),
            )

    async def _tool_is_allowed(self, server_config: MCPServerConfig, tool_name: str) -> bool:
        cached_tools = self._tool_cache.get(server_config.name)
        if cached_tools is not None:
            return tool_name in cached_tools

        try:
            tools = await self._list_tools(server_config)
            self._tool_cache[server_config.name] = tools
            return tool_name in tools
        except Exception as exc:
            logger.debug("MCP tool discovery failed for %s: %s", server_config.name, exc)
            return True

    async def _list_tools(self, server_config: MCPServerConfig) -> set[str]:
        async def _with_session(session: Any) -> set[str]:
            await session.initialize()
            response = await asyncio.wait_for(session.list_tools(), timeout=self.timeout_seconds)
            return {tool.name for tool in getattr(response, "tools", [])}

        if server_config.transport == "stdio":
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            params = StdioServerParameters(command=server_config.command, args=server_config.args)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    return await _with_session(session)

        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(server_config.url) as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as session:
                return await _with_session(session)

    async def _call_stdio_tool(self, server_config: MCPServerConfig, tool_name: str, arguments: Dict[str, Any]) -> Any:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=server_config.command, args=server_config.args)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=arguments),
                    timeout=self.timeout_seconds,
                )
                return result

    async def _call_http_tool(self, server_config: MCPServerConfig, tool_name: str, arguments: Dict[str, Any]) -> Any:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(server_config.url) as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=arguments),
                    timeout=self.timeout_seconds,
                )
                return result

    def _build_arguments(self, route: MCPToolRoute, params: Dict[str, Any]) -> Dict[str, Any]:
        arguments = dict(route.defaults)
        for source_key, target_key in route.argument_map.items():
            value = params.get(source_key)
            if value is not None:
                value = self._transform_argument(route, source_key, value)
                arguments[target_key] = value
        return {key: value for key, value in arguments.items() if value is not None}

    def _transform_argument(self, route: MCPToolRoute, source_key: str, value: Any) -> Any:
        if source_key == "symbol":
            if route.transform == "finance":
                return to_tushare_ts_code(value)
            if route.transform == "china_stock":
                return to_plain_a_share_code(value)
            if route.transform == "stock_mcp":
                return to_stock_mcp_symbol(value)
        if source_key in {"start_date", "end_date"} and route.transform == "finance":
            return to_yyyymmdd(value)
        if source_key == "period" and route.transform == "stock_mcp":
            return to_stock_mcp_period(value)
        return value

    def _load_server_configs(self) -> Dict[str, MCPServerConfig]:
        configs: Dict[str, MCPServerConfig] = {}
        self._add_stdio_or_http_config(
            configs,
            "china_stock_mcp",
            "MCP_CHINA_STOCK",
            command_envs=("MCP_CHINA_STOCK_COMMAND", "MCP_CHINA_STOCK_CMD", "CHINA_STOCK_MCP_COMMAND"),
            url_envs=("MCP_CHINA_STOCK_URL", "CHINA_STOCK_MCP_URL"),
            default_url="http://localhost:8081/mcp",
        )
        self._add_stdio_or_http_config(
            configs,
            "finance_mcp",
            "MCP_FINANCE",
            command_envs=("MCP_FINANCE_COMMAND", "MCP_FINANCE_CMD", "FINANCE_MCP_COMMAND"),
            url_envs=("MCP_FINANCE_URL", "FINANCE_MCP_URL"),
            default_url="http://localhost:3000/mcp",
        )
        self._add_stdio_or_http_config(
            configs,
            "tushare_mcp",
            "MCP_TUSHARE",
            command_envs=("MCP_TUSHARE_COMMAND", "MCP_TUSHARE_CMD", "TUSHARE_MCP_COMMAND"),
            url_envs=("MCP_TUSHARE_URL", "TUSHARE_MCP_URL"),
        )
        return configs

    def _add_stdio_or_http_config(
        self,
        configs: Dict[str, MCPServerConfig],
        name: str,
        prefix: str,
        command_envs: Iterable[str],
        url_envs: Iterable[str],
        default_url: Optional[str] = None,
    ) -> None:
        transport = os.getenv(f"{prefix}_TRANSPORT", "stdio").lower()
        url = _first_env(url_envs) or (default_url if transport in {"streamable_http", "http"} else None)
        command = _first_env(command_envs)
        args = _parse_args(os.getenv(f"{prefix}_ARGS", ""))

        if transport in {"streamable_http", "http"}:
            if url:
                configs[name] = MCPServerConfig(name=name, transport=transport, url=url)
            return

        if command:
            configs[name] = MCPServerConfig(name=name, transport="stdio", command=command, args=args)

    def _normalize_content(self, result: Any) -> Any:
        if hasattr(result, "content"):
            result = result.content

        if isinstance(result, list):
            normalized_items = [self._normalize_content(item) for item in result]
            if len(normalized_items) == 1:
                return normalized_items[0]
            return normalized_items

        text = getattr(result, "text", None)
        if text is not None:
            return _parse_json_if_possible(text)

        data = getattr(result, "data", None)
        if data is not None:
            return data

        if isinstance(result, str):
            return _parse_json_if_possible(result)
        return result

    def _mcp_package_available(self) -> bool:
        try:
            import mcp  # noqa: F401

            return True
        except Exception:
            return False


def _first_env(names: Iterable[str]) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _parse_args(value: str) -> List[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except Exception:
        pass
    return shlex.split(value)


def _parse_json_if_possible(value: str) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return value


def to_plain_a_share_code(symbol: Any) -> str:
    code = str(symbol or "").strip().upper()
    for suffix in (".SH", ".SZ", ".SS", ".XSHE", ".XSHG"):
        if code.endswith(suffix):
            code = code[: -len(suffix)]
            break
    return code


def to_tushare_ts_code(symbol: Any) -> str:
    code = to_plain_a_share_code(symbol)
    if "." in str(symbol or "") and len(code) == 6:
        original = str(symbol).strip().upper()
        if original.endswith((".SH", ".XSHG")):
            return f"{code}.SH"
        if original.endswith((".SZ", ".XSHE")):
            return f"{code}.SZ"
    if code.startswith(("5", "6", "9")):
        return f"{code}.SH"
    return f"{code}.SZ"


def to_stock_mcp_symbol(symbol: Any) -> str:
    code = to_plain_a_share_code(symbol)
    if "." in str(symbol or "") and len(code) == 6:
        original = str(symbol).strip().upper()
        if original.endswith((".SH", ".XSHG")):
            return f"{code}.SH"
        if original.endswith((".SZ", ".XSHE")):
            return f"{code}.SZ"
    if len(code) == 6 and code.startswith(("5", "6", "9")):
        return f"{code}.SH"
    if len(code) == 6:
        return f"{code}.SZ"
    return code


def to_stock_mcp_period(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "daily": "1y",
        "day": "1y",
        "d": "1y",
        "weekly": "2y",
        "week": "2y",
        "w": "2y",
        "monthly": "5y",
        "month": "5y",
        "m": "5y",
    }
    return mapping.get(raw, raw or "1y")


def to_yyyymmdd(value: Any) -> Any:
    if value is None:
        return None
    return str(value).replace("-", "")


def _run_async_safely(coro: Any) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    if not loop.is_running():
        return loop.run_until_complete(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


_mcp_data_gateway: Optional[MCPDataGateway] = None


def get_mcp_data_gateway() -> MCPDataGateway:
    global _mcp_data_gateway
    if _mcp_data_gateway is None:
        _mcp_data_gateway = MCPDataGateway()
    return _mcp_data_gateway
