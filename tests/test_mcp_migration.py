def test_mcp_gateway_fails_closed_without_package(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "true")
    from tradingagents.dataflows.mcp.gateway import MCPDataGateway

    gateway = MCPDataGateway()
    result = gateway.call("news", symbol="000001", params={"limit": 1})

    assert not result.ok
    assert "mcp" in (result.error or "").lower()


def test_mcp_china_datasource_enum_and_default_order(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "false")
    from tradingagents.constants import DataSourceCode
    from tradingagents.dataflows.data_source_manager import ChinaDataSource, DataSourceManager

    manager = object.__new__(DataSourceManager)
    manager.available_sources = [
        ChinaDataSource.MCP_CHINA,
        ChinaDataSource.TUSHARE,
        ChinaDataSource.AKSHARE,
        ChinaDataSource.BAOSTOCK,
    ]

    assert DataSourceCode.MCP_CHINA == "mcp_china"
    assert manager._get_data_source_priority_order("000001")[0] == ChinaDataSource.MCP_CHINA


def test_http_defaults_and_argument_transforms(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setenv("MCP_FINANCE_TRANSPORT", "streamable_http")
    monkeypatch.delenv("MCP_FINANCE_URL", raising=False)
    monkeypatch.setenv("MCP_CHINA_STOCK_TRANSPORT", "streamable_http")
    monkeypatch.delenv("MCP_CHINA_STOCK_URL", raising=False)

    from tradingagents.dataflows.mcp.gateway import (
        MCPDataGateway,
        MCPToolRoute,
        to_plain_a_share_code,
        to_tushare_ts_code,
        to_yyyymmdd,
    )

    gateway = MCPDataGateway()
    servers = gateway.list_configured_servers()

    assert servers["finance_mcp"].url == "http://localhost:3000/mcp"
    assert servers["china_stock_mcp"].url == "http://localhost:8081/mcp"
    assert to_plain_a_share_code("600519.SH") == "600519"
    assert to_tushare_ts_code("600519") == "600519.SH"
    assert to_tushare_ts_code("000001") == "000001.SZ"
    assert to_yyyymmdd("2026-05-12") == "20260512"

    route = MCPToolRoute(
        "finance_mcp",
        "company_performance",
        {"symbol": "ts_code", "start_date": "start_date"},
        transform="finance",
    )
    assert gateway._build_arguments(route, {"symbol": "000001", "start_date": "2026-05-12"}) == {
        "ts_code": "000001.SZ",
        "start_date": "20260512",
    }


def test_mcp_smoke_tools_list_fails_closed(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setenv("MCP_FINANCE_TRANSPORT", "streamable_http")
    monkeypatch.setenv("MCP_FINANCE_URL", "http://localhost:3000/mcp")

    from tradingagents.dataflows.mcp.gateway import MCPDataGateway

    result = MCPDataGateway().list_tools("finance_mcp")
    assert result.tool == "tools/list"
    if not result.ok:
        assert result.error


def test_a_share_mode_tool_nodes_only_expose_unified_tools():
    pytest = __import__("pytest")
    pytest.importorskip("langchain_core")

    from tradingagents.agents.utils.agent_utils import Toolkit
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    graph = object.__new__(TradingAgentsGraph)
    graph.config = {**DEFAULT_CONFIG, "a_share_mode": True}
    graph.toolkit = Toolkit(graph.config)

    nodes = graph._create_tool_nodes()
    expected = {
        "market": ["get_stock_market_data_unified"],
        "social": ["get_stock_sentiment_unified"],
        "news": ["get_stock_news_unified"],
        "fundamentals": ["get_stock_fundamentals_unified"],
    }

    for key, tool_names in expected.items():
        actual = [tool.name for tool in nodes[key].tools_by_name.values()]
        assert actual == tool_names
