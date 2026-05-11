import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_dir": os.path.join(os.path.expanduser("~"), "Documents", "TradingAgents", "data"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "o4-mini",
    "quick_think_llm": "gpt-4o-mini",
    "backend_url": "https://api.openai.com/v1",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Tool settings - 从环境变量读取，提供默认值
    "online_tools": os.getenv("ONLINE_TOOLS_ENABLED", "false").lower() == "true",
    "online_news": os.getenv("ONLINE_NEWS_ENABLED", "true").lower() == "true",
    "realtime_data": os.getenv("REALTIME_DATA_ENABLED", "false").lower() == "true",
    "mcp_enabled": os.getenv("MCP_ENABLED", "true").lower() == "true",
    "mcp_legacy_fallback_enabled": os.getenv("MCP_LEGACY_FALLBACK_ENABLED", "true").lower() == "true",
    "mcp_timeout_seconds": int(os.getenv("MCP_TIMEOUT_SECONDS", "30")),
    "mcp_primary_news": os.getenv("MCP_PRIMARY_NEWS", "finance_mcp"),
    "mcp_primary_market": os.getenv("MCP_PRIMARY_MARKET", "china_stock_mcp"),

    # Note: Database and cache configuration is now managed by .env file and config.database_manager
    # No database/cache settings in default config to avoid configuration conflicts
}
