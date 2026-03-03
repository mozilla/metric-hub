"""MCP server for Mozilla Metric Hub."""

import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    EmbeddedResource,
    ImageContent,
    TextContent,
    Tool,
)

from .experiments import (
    handle_create_experiment_config,
    handle_generate_config_template,
    handle_get_experiment,
    handle_get_experiment_config,
    handle_list_experiment_configs,
    handle_list_experiments,
)
from .funnels import (
    handle_build_funnel_url,
    handle_get_glean_event,
    handle_list_glean_event_categories,
    handle_search_glean_events,
)
from .metrics import (
    handle_generate_metric_template,
    handle_get_data_source,
    handle_get_metric,
    handle_get_metric_sql,
    handle_get_segment,
    handle_list_data_sources,
    handle_list_metrics,
    handle_list_platforms,
    handle_list_segments,
    handle_search_metrics,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Server("metric-hub")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_platforms",
            description="List all available platforms/products that have metric definitions",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="list_metrics",
            description="List all metrics for a specific platform",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "description": "Platform name (e.g., 'firefox_desktop', 'fenix', 'ads')"},
                    "category": {"type": "string", "description": "Optional: filter by category (e.g., 'search', 'performance')"},
                },
                "required": ["platform"],
            },
        ),
        Tool(
            name="get_metric",
            description="Get detailed information about a specific metric",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "description": "Platform name"},
                    "metric_name": {"type": "string", "description": "Name of the metric"},
                },
                "required": ["platform", "metric_name"],
            },
        ),
        Tool(
            name="list_data_sources",
            description="List all data sources for a specific platform",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "description": "Platform name"},
                },
                "required": ["platform"],
            },
        ),
        Tool(
            name="get_data_source",
            description="Get detailed information about a specific data source",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "description": "Platform name"},
                    "data_source_name": {"type": "string", "description": "Name of the data source"},
                },
                "required": ["platform", "data_source_name"],
            },
        ),
        Tool(
            name="search_metrics",
            description="Search for metrics across all platforms by name or description",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "platform": {"type": "string", "description": "Optional: limit search to a specific platform"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="generate_metric_template",
            description="Generate a template for creating a new metric definition",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric_name": {"type": "string", "description": "Name for the new metric (snake_case)"},
                    "data_source": {"type": "string", "description": "Data source to use"},
                    "metric_type": {
                        "type": "string",
                        "description": "Type of metric: 'simple', 'derived', or 'custom'",
                        "enum": ["simple", "derived", "custom"],
                    },
                },
                "required": ["metric_name", "data_source", "metric_type"],
            },
        ),
        Tool(
            name="get_metric_sql",
            description="Generate SQL query for a metric",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "description": "Platform name"},
                    "metric_name": {"type": "string", "description": "Name of the metric"},
                },
                "required": ["platform", "metric_name"],
            },
        ),
        Tool(
            name="list_experiment_configs",
            description="List configuration files. Use 'jetstream' for experiment configs, 'opmon' for operational monitoring, 'looker' for Looker configs",
            inputSchema={
                "type": "object",
                "properties": {
                    "config_type": {
                        "type": "string",
                        "description": "Type of configs: 'jetstream', 'opmon', or 'looker'",
                        "enum": ["jetstream", "opmon", "looker"],
                    },
                },
                "required": ["config_type"],
            },
        ),
        Tool(
            name="get_experiment_config",
            description="Get the contents of an existing configuration file from jetstream/, opmon/, or looker/ folders",
            inputSchema={
                "type": "object",
                "properties": {
                    "config_type": {
                        "type": "string",
                        "enum": ["jetstream", "opmon", "looker"],
                    },
                    "config_slug": {"type": "string", "description": "Config slug (filename without .toml extension)"},
                },
                "required": ["config_type", "config_slug"],
            },
        ),
        Tool(
            name="create_experiment_config",
            description="Create a new config file in jetstream/, opmon/, or looker/ folder",
            inputSchema={
                "type": "object",
                "properties": {
                    "new_config_slug": {"type": "string", "description": "Slug for the new config"},
                    "config_type": {
                        "type": "string",
                        "enum": ["jetstream", "opmon", "looker"],
                    },
                    "base_config_slug": {"type": "string", "description": "Optional: existing config slug to copy from"},
                    "config_content": {"type": "string", "description": "Optional: TOML content for the new config"},
                },
                "required": ["new_config_slug", "config_type"],
            },
        ),
        Tool(
            name="generate_config_template",
            description="Generate a template for a new configuration (jetstream experiment, opmon monitoring, or looker dashboard)",
            inputSchema={
                "type": "object",
                "properties": {
                    "config_type": {
                        "type": "string",
                        "enum": ["jetstream", "opmon", "looker"],
                    },
                    "template_type": {
                        "type": "string",
                        "description": "Template type. jetstream: 'basic', 'with_segments', 'with_custom_metrics', 'with_custom_data_source'. opmon: 'basic', 'with_dimensions'. looker: 'basic'",
                    },
                    "platform": {"type": "string", "description": "Platform name"},
                },
                "required": ["config_type", "template_type", "platform"],
            },
        ),
        Tool(
            name="list_segments",
            description="List all segments for a specific platform",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "description": "Platform name"},
                },
                "required": ["platform"],
            },
        ),
        Tool(
            name="get_segment",
            description="Get detailed information about a specific segment",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "description": "Platform name"},
                    "segment_name": {"type": "string", "description": "Name of the segment"},
                },
                "required": ["platform", "segment_name"],
            },
        ),
        Tool(
            name="list_glean_event_categories",
            description="List all Glean event categories for a product. Use this to orient when you don't know where to start.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product": {
                        "type": "string",
                        "description": "Platform name (e.g. 'firefox_desktop', 'fenix'). Defaults to 'firefox_desktop'.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="search_glean_events",
            description="Search Glean events for a product by name, category, description, or tag. Returns event_category, event_name, and BigQuery details needed to build a funnel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term (e.g. 'tab group', 'create', 'save')"},
                    "product": {
                        "type": "string",
                        "description": "Platform name (e.g. 'firefox_desktop', 'fenix'). Defaults to 'firefox_desktop'.",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_glean_event",
            description="Get full details for a specific Glean event including BigQuery table, filter, and extra keys.",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric_name": {
                        "type": "string",
                        "description": "Full metric name (e.g. 'tabgroup.create_group')",
                    },
                    "product": {
                        "type": "string",
                        "description": "Platform name. Defaults to 'firefox_desktop'.",
                    },
                },
                "required": ["metric_name"],
            },
        ),
        Tool(
            name="build_funnel_url",
            description="Generate a Looker event_funnel explore URL pre-populated with funnel steps. Validates events against the Glean dictionary. Supports up to 4 steps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "description": "Ordered funnel steps. Each step needs event_category, event_name, and optionally label and description.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "event_category": {"type": "string"},
                                "event_name": {"type": "string"},
                                "label": {"type": "string", "description": "Snake_case label for this step (e.g. 'created', 'saved')"},
                                "description": {"type": "string"},
                                "extra": {
                                    "type": "object",
                                    "description": "Optional extra key filter for this step.",
                                    "properties": {
                                        "key": {"type": "string", "description": "Extra field path, e.g. 'strings.action', 'booleans.checked', 'quantities.duration_ms'"},
                                        "value": {"type": "string", "description": "Value to filter on"},
                                    },
                                    "required": ["key", "value"],
                                },
                            },
                            "required": ["event_category", "event_name"],
                        },
                    },
                    "product": {
                        "type": "string",
                        "description": "Platform name. Defaults to 'firefox_desktop'.",
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional filters to apply to all steps.",
                        "properties": {
                            "country": {
                                "oneOf": [
                                    {"type": "string"},
                                    {"type": "array", "items": {"type": "string"}},
                                ],
                                "description": "Country code(s) (e.g. 'US' or ['US', 'CA'])",
                            },
                            "channel": {"type": "string", "description": "Release channel (e.g. 'release', 'beta', 'nightly')"},
                            "os": {"type": "string", "description": "Operating system (e.g. 'Windows', 'Mac', 'Linux')"},
                        },
                    },
                },
                "required": ["steps"],
            },
        ),
        Tool(
            name="list_experiments",
            description="List experiments and rollouts from Experimenter API",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status: 'Live' or 'Complete'"},
                    "app_name": {"type": "string", "description": "Filter by application name"},
                    "is_rollout": {"type": "boolean", "description": "Filter to rollouts (true) or experiments (false)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_experiment",
            description="Get detailed information about a specific experiment or rollout from Experimenter",
            inputSchema={
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Experiment slug"},
                },
                "required": ["slug"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent | ImageContent | EmbeddedResource]:
    try:
        match name:
            case "list_platforms":
                return await handle_list_platforms()
            case "list_metrics":
                return await handle_list_metrics(arguments)
            case "get_metric":
                return await handle_get_metric(arguments)
            case "list_data_sources":
                return await handle_list_data_sources(arguments)
            case "get_data_source":
                return await handle_get_data_source(arguments)
            case "search_metrics":
                return await handle_search_metrics(arguments)
            case "generate_metric_template":
                return await handle_generate_metric_template(arguments)
            case "get_metric_sql":
                return await handle_get_metric_sql(arguments)
            case "list_experiment_configs":
                return await handle_list_experiment_configs(arguments)
            case "get_experiment_config":
                return await handle_get_experiment_config(arguments)
            case "create_experiment_config":
                return await handle_create_experiment_config(arguments)
            case "generate_config_template":
                return await handle_generate_config_template(arguments)
            case "list_segments":
                return await handle_list_segments(arguments)
            case "get_segment":
                return await handle_get_segment(arguments)
            case "list_glean_event_categories":
                return await handle_list_glean_event_categories(arguments)
            case "search_glean_events":
                return await handle_search_glean_events(arguments)
            case "get_glean_event":
                return await handle_get_glean_event(arguments)
            case "build_funnel_url":
                return await handle_build_funnel_url(arguments)
            case "list_experiments":
                return await handle_list_experiments(arguments)
            case "get_experiment":
                return await handle_get_experiment(arguments)
            case _:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main() -> None:
    """Run the MCP server via stdio (local mode)."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


async def run_sse_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Run the MCP server via HTTP SSE (Cloud Run mode)."""
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Route
    import uvicorn

    async def handle_sse(_request):
        async with SseServerTransport("/messages") as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
            return Response()

    async def handle_messages(_request):
        async with SseServerTransport("/messages") as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
            return Response()

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
        ]
    )

    config = uvicorn.Config(starlette_app, host=host, port=port, log_level="info")
    await uvicorn.Server(config).serve()


def cli() -> None:
    """CLI entry point for local stdio mode."""
    import asyncio
    asyncio.run(main())


def cli_http() -> None:
    """CLI entry point for HTTP/SSE mode (Cloud Run)."""
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Run Metric Hub MCP Server in HTTP/SSE mode")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    args = parser.parse_args()

    logger.info(f"Starting Metric Hub MCP Server on {args.host}:{args.port}")
    asyncio.run(run_sse_server(host=args.host, port=args.port))


if __name__ == "__main__":
    cli_http()
