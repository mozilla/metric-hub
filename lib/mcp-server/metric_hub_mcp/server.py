"""MCP server for Mozilla Metric Hub.

This server provides tools to query, create, and validate metrics from the metric-hub repository.
"""

import logging
import time
from pathlib import Path
from typing import Any

import requests
import toml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

from metric_config_parser.config import ConfigCollection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global config collection
_config_collection: ConfigCollection | None = None
_repo_path: Path | None = None

# Experimenter API configuration
EXPERIMENTER_API_URL = "https://experimenter.services.mozilla.com/api/v8/experiments/"
MAX_RETRIES = 3


def get_config_collection() -> ConfigCollection:
    """Get or initialize the config collection."""
    global _config_collection, _repo_path

    if _config_collection is None:
        # Try to load from local repo (parent directory of mcp-server)
        if _repo_path is None:
            _repo_path = Path(__file__).parent.parent.parent.parent

        logger.info(f"Loading metric hub configs from {_repo_path}")
        _config_collection = ConfigCollection.from_github_repo(
            "https://github.com/mozilla/metric-hub"
        )

    return _config_collection


def retry_get(url: str, max_retries: int = MAX_RETRIES) -> Any:
    """Fetch JSON data from URL with retry logic."""
    session = requests.Session()
    session.headers.update({"User-Agent": "metric-hub-mcp"})

    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.info(f"Attempt {attempt + 1}/{max_retries} failed for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                raise Exception(f"Failed to fetch {url} after {max_retries} retries") from e


def fetch_experiments_from_experimenter() -> list[dict[str, Any]]:
    """Fetch all experiments from Experimenter API."""
    try:
        experiments_json = retry_get(EXPERIMENTER_API_URL)
        return experiments_json
    except Exception as e:
        logger.error(f"Error fetching experiments from Experimenter: {e}")
        return []


# Create MCP server
app = Server("metric-hub")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="list_platforms",
            description="List all available platforms/products that have metric definitions",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="list_metrics",
            description="List all metrics for a specific platform",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Platform name (e.g., 'firefox_desktop', 'fenix', 'ads')",
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional: filter by category (e.g., 'search', 'performance')",
                    },
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
                    "platform": {
                        "type": "string",
                        "description": "Platform name (e.g., 'firefox_desktop', 'fenix')",
                    },
                    "metric_name": {
                        "type": "string",
                        "description": "Name of the metric",
                    },
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
                    "platform": {
                        "type": "string",
                        "description": "Platform name (e.g., 'firefox_desktop', 'fenix')",
                    },
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
                    "platform": {
                        "type": "string",
                        "description": "Platform name (e.g., 'firefox_desktop', 'fenix')",
                    },
                    "data_source_name": {
                        "type": "string",
                        "description": "Name of the data source",
                    },
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
                    "query": {
                        "type": "string",
                        "description": "Search query to match against metric names and descriptions",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Optional: limit search to a specific platform",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="validate_metric_config",
            description="Validate a metric configuration (TOML format)",
            inputSchema={
                "type": "object",
                "properties": {
                    "config_toml": {
                        "type": "string",
                        "description": "TOML configuration string to validate",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform name for context",
                    },
                },
                "required": ["config_toml", "platform"],
            },
        ),
        Tool(
            name="generate_metric_template",
            description="Generate a template for creating a new metric definition",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric_name": {
                        "type": "string",
                        "description": "Name for the new metric (snake_case)",
                    },
                    "data_source": {
                        "type": "string",
                        "description": "Data source to use",
                    },
                    "metric_type": {
                        "type": "string",
                        "description": "Type of metric: 'simple' (single field aggregation), 'derived' (computed from other metrics), or 'custom' (custom SQL)",
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
                    "platform": {
                        "type": "string",
                        "description": "Platform name (e.g., 'firefox_desktop')",
                    },
                    "metric_name": {
                        "type": "string",
                        "description": "Name of the metric",
                    },
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
                        "description": "Type of configs: 'jetstream' (experiment configs), 'opmon' (operational monitoring), 'looker' (Looker dashboards)",
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
                        "description": "Type of config: 'jetstream' (experiments), 'opmon' (monitoring), 'looker' (dashboards)",
                        "enum": ["jetstream", "opmon", "looker"],
                    },
                    "config_slug": {
                        "type": "string",
                        "description": "Config slug (filename without .toml extension)",
                    },
                },
                "required": ["config_type", "config_slug"],
            },
        ),
        Tool(
            name="create_experiment_config",
            description="Create a new config file in jetstream/, opmon/, or looker/ folder. NOTE: For metric/data source definitions, use generate_metric_template instead",
            inputSchema={
                "type": "object",
                "properties": {
                    "new_config_slug": {
                        "type": "string",
                        "description": "Slug for the new config (will be filename without .toml)",
                    },
                    "config_type": {
                        "type": "string",
                        "description": "Type: 'jetstream' (experiments), 'opmon' (monitoring), 'looker' (dashboards). NOT for metric definitions (use definitions/ folder tools)",
                        "enum": ["jetstream", "opmon", "looker"],
                    },
                    "base_config_slug": {
                        "type": "string",
                        "description": "Optional: existing config slug to copy from",
                    },
                    "config_content": {
                        "type": "string",
                        "description": "Optional: TOML content for the new config (if not copying from base)",
                    },
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
                        "description": "Type of config: 'jetstream' (experiments), 'opmon' (monitoring), 'looker' (dashboards)",
                        "enum": ["jetstream", "opmon", "looker"],
                    },
                    "template_type": {
                        "type": "string",
                        "description": "Template type: For jetstream: 'basic', 'with_segments', 'with_custom_metrics', 'with_custom_data_source'. For opmon: 'basic', 'with_dimensions'. For looker: 'basic'",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform name (e.g., 'firefox_desktop', 'fenix')",
                    },
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
                    "platform": {
                        "type": "string",
                        "description": "Platform name (e.g., 'firefox_desktop', 'fenix')",
                    },
                },
                "required": ["platform"],
            },
        ),
        Tool(
            name="list_experiments",
            description="List experiments and rollouts from Experimenter API",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: 'Live', 'Complete', or omit for all launched experiments",
                    },
                    "app_name": {
                        "type": "string",
                        "description": "Filter by application name (e.g., 'firefox_desktop', 'fenix')",
                    },
                    "is_rollout": {
                        "type": "boolean",
                        "description": "Filter to show only rollouts (true) or only experiments (false), or omit for both",
                    },
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
                    "slug": {
                        "type": "string",
                        "description": "Experiment slug (normandy_slug or experimenter_slug)",
                    },
                },
                "required": ["slug"],
            },
        ),
        Tool(
            name="get_segment",
            description="Get detailed information about a specific segment",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Platform name (e.g., 'firefox_desktop', 'fenix')",
                    },
                    "segment_name": {
                        "type": "string",
                        "description": "Name of the segment",
                    },
                },
                "required": ["platform", "segment_name"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls."""
    try:
        if name == "list_platforms":
            return await handle_list_platforms()
        elif name == "list_metrics":
            return await handle_list_metrics(arguments)
        elif name == "get_metric":
            return await handle_get_metric(arguments)
        elif name == "list_data_sources":
            return await handle_list_data_sources(arguments)
        elif name == "get_data_source":
            return await handle_get_data_source(arguments)
        elif name == "search_metrics":
            return await handle_search_metrics(arguments)
        elif name == "validate_metric_config":
            return await handle_validate_metric_config(arguments)
        elif name == "generate_metric_template":
            return await handle_generate_metric_template(arguments)
        elif name == "get_metric_sql":
            return await handle_get_metric_sql(arguments)
        elif name == "list_experiment_configs":
            return await handle_list_experiment_configs(arguments)
        elif name == "get_experiment_config":
            return await handle_get_experiment_config(arguments)
        elif name == "create_experiment_config":
            return await handle_create_experiment_config(arguments)
        elif name == "generate_config_template":
            return await handle_generate_config_template(arguments)
        elif name == "list_segments":
            return await handle_list_segments(arguments)
        elif name == "get_segment":
            return await handle_get_segment(arguments)
        elif name == "list_experiments":
            return await handle_list_experiments(arguments)
        elif name == "get_experiment":
            return await handle_get_experiment_from_experimenter(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_list_platforms() -> list[TextContent]:
    """List all available platforms."""
    config = get_config_collection()

    # Get all definition configs
    platforms = []
    for definition_config in config.definitions:
        platforms.append({
            "name": definition_config.slug,
            "metrics_count": len(definition_config.spec.metrics.definitions or {}),
            "data_sources_count": len(definition_config.spec.data_sources.definitions or {}),
        })

    result = "# Available Platforms\n\n"
    for platform in sorted(platforms, key=lambda x: x["name"]):
        result += f"## {platform['name']}\n"
        result += f"- Metrics: {platform['metrics_count']}\n"
        result += f"- Data Sources: {platform['data_sources_count']}\n\n"

    return [TextContent(type="text", text=result)]


async def handle_list_metrics(arguments: dict[str, Any]) -> list[TextContent]:
    """List all metrics for a platform."""
    platform = arguments["platform"]
    category_filter = arguments.get("category")

    config = get_config_collection()

    try:
        definition_config = config.get_platform_definitions(platform)
    except Exception as e:
        return [TextContent(type="text", text=f"Platform '{platform}' not found. Use list_platforms to see available platforms.")]

    if not definition_config or not definition_config.metrics or not definition_config.metrics.definitions:
        return [TextContent(type="text", text=f"No metrics found for platform '{platform}'")]

    # Filter and format metrics
    metrics = []
    for metric_name, metric_def in definition_config.metrics.definitions.items():
        if category_filter and getattr(metric_def, "category", None) != category_filter:
            continue

        description = getattr(metric_def, "description", "") or ""
        category = getattr(metric_def, "category", "uncategorized") or "uncategorized"
        metrics.append({
            "name": metric_name,
            "friendly_name": getattr(metric_def, "friendly_name", metric_name),
            "category": category,
            "data_source": getattr(metric_def, "data_source", None),
            "description": description.split("\n")[0][:100],
        })

    result = f"# Metrics for {platform}\n\n"
    if category_filter:
        result += f"**Category filter:** {category_filter}\n\n"

    result += f"**Total metrics:** {len(metrics)}\n\n"

    # Group by category
    by_category: dict[str, list] = {}
    for metric in metrics:
        cat = metric["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(metric)

    for category in sorted(by_category.keys()):
        result += f"## {category}\n\n"
        for metric in sorted(by_category[category], key=lambda x: x["name"]):
            result += f"### {metric['name']}\n"
            result += f"- **Friendly Name:** {metric['friendly_name']}\n"
            if metric['data_source']:
                result += f"- **Data Source:** {metric['data_source']}\n"
            if metric['description']:
                result += f"- **Description:** {metric['description']}...\n"
            result += "\n"

    return [TextContent(type="text", text=result)]


async def handle_get_metric(arguments: dict[str, Any]) -> list[TextContent]:
    """Get detailed information about a metric."""
    platform = arguments["platform"]
    metric_name = arguments["metric_name"]

    config = get_config_collection()

    try:
        metric_def = config.get_metric_definition(metric_name, platform)
    except Exception as e:
        return [TextContent(type="text", text=f"Metric '{metric_name}' not found in platform '{platform}': {e}")]

    result = f"# Metric: {metric_name}\n\n"
    result += f"**Platform:** {platform}\n\n"

    if hasattr(metric_def, "friendly_name"):
        result += f"**Friendly Name:** {metric_def.friendly_name}\n\n"

    if hasattr(metric_def, "description") and metric_def.description:
        result += f"## Description\n\n{metric_def.description}\n\n"

    if hasattr(metric_def, "category"):
        result += f"**Category:** {metric_def.category}\n\n"

    if hasattr(metric_def, "type"):
        result += f"**Type:** {metric_def.type}\n\n"

    if hasattr(metric_def, "data_source") and metric_def.data_source:
        result += f"**Data Source:** {metric_def.data_source}\n\n"

    if hasattr(metric_def, "select_expression") and metric_def.select_expression:
        result += f"## Select Expression\n\n```sql\n{metric_def.select_expression}\n```\n\n"

    if hasattr(metric_def, "depends_on") and metric_def.depends_on:
        result += f"**Depends On:** {', '.join(metric_def.depends_on)}\n\n"

    if hasattr(metric_def, "bigger_is_better"):
        result += f"**Bigger is Better:** {metric_def.bigger_is_better}\n\n"

    if hasattr(metric_def, "owner") and metric_def.owner:
        result += f"**Owner:** {', '.join(metric_def.owner)}\n\n"

    if hasattr(metric_def, "deprecated") and metric_def.deprecated:
        result += f"**⚠️ DEPRECATED:** {metric_def.deprecated}\n\n"

    return [TextContent(type="text", text=result)]


async def handle_list_data_sources(arguments: dict[str, Any]) -> list[TextContent]:
    """List all data sources for a platform."""
    platform = arguments["platform"]

    config = get_config_collection()

    try:
        definition_config = config.get_platform_definitions(platform)
    except Exception:
        return [TextContent(type="text", text=f"Platform '{platform}' not found")]

    if not definition_config or not definition_config.data_sources or not definition_config.data_sources.definitions:
        return [TextContent(type="text", text=f"No data sources found for platform '{platform}'")]

    result = f"# Data Sources for {platform}\n\n"

    for ds_name, ds_def in sorted(definition_config.data_sources.definitions.items()):
        result += f"## {ds_name}\n"

        if hasattr(ds_def, "friendly_name"):
            result += f"**Friendly Name:** {ds_def.friendly_name}\n\n"

        if hasattr(ds_def, "from_expression"):
            result += f"**From:** `{ds_def.from_expression}`\n\n"

        if hasattr(ds_def, "description") and ds_def.description:
            result += f"{ds_def.description}\n\n"

        if hasattr(ds_def, "experiments_column_type"):
            result += f"**Experiments Column Type:** {ds_def.experiments_column_type}\n\n"

        result += "\n"

    return [TextContent(type="text", text=result)]


async def handle_get_data_source(arguments: dict[str, Any]) -> list[TextContent]:
    """Get detailed information about a data source."""
    platform = arguments["platform"]
    data_source_name = arguments["data_source_name"]

    config = get_config_collection()

    try:
        ds_def = config.get_data_source_definition(data_source_name, platform)
    except Exception as e:
        return [TextContent(type="text", text=f"Data source '{data_source_name}' not found in platform '{platform}': {e}")]

    result = f"# Data Source: {data_source_name}\n\n"
    result += f"**Platform:** {platform}\n\n"

    if hasattr(ds_def, "friendly_name"):
        result += f"**Friendly Name:** {ds_def.friendly_name}\n\n"

    if hasattr(ds_def, "description") and ds_def.description:
        result += f"## Description\n\n{ds_def.description}\n\n"

    if hasattr(ds_def, "from_expression"):
        result += f"## From Expression\n\n```sql\n{ds_def.from_expression}\n```\n\n"

    result += "## Configuration\n\n"

    if hasattr(ds_def, "experiments_column_type"):
        result += f"- **Experiments Column Type:** {ds_def.experiments_column_type}\n"

    if hasattr(ds_def, "client_id_column"):
        result += f"- **Client ID Column:** {ds_def.client_id_column}\n"

    if hasattr(ds_def, "submission_date_column"):
        result += f"- **Submission Date Column:** {ds_def.submission_date_column}\n"

    if hasattr(ds_def, "default_dataset"):
        result += f"- **Default Dataset:** {ds_def.default_dataset}\n"

    if hasattr(ds_def, "build_id_column"):
        result += f"- **Build ID Column:** {ds_def.build_id_column}\n"

    if hasattr(ds_def, "group_id_column"):
        result += f"- **Group ID Column:** {ds_def.group_id_column}\n"

    if hasattr(ds_def, "analysis_units") and ds_def.analysis_units:
        result += f"- **Analysis Units:** {', '.join(ds_def.analysis_units)}\n"

    if hasattr(ds_def, "columns_as_dimensions"):
        result += f"- **Columns as Dimensions:** {ds_def.columns_as_dimensions}\n"

    return [TextContent(type="text", text=result)]


async def handle_search_metrics(arguments: dict[str, Any]) -> list[TextContent]:
    """Search for metrics by name or description."""
    query = arguments["query"].lower()
    platform_filter = arguments.get("platform")

    config = get_config_collection()

    results = []

    for definition_config in config.definitions:
        platform_name = definition_config.slug
        if platform_filter and platform_name != platform_filter:
            continue

        if not definition_config.spec.metrics.definitions:
            continue

        for metric_name, metric_def in definition_config.spec.metrics.definitions.items():
            # Search in name
            if query in metric_name.lower():
                match_type = "name"
            # Search in friendly name
            elif hasattr(metric_def, "friendly_name") and metric_def.friendly_name and query in metric_def.friendly_name.lower():
                match_type = "friendly_name"
            # Search in description
            elif hasattr(metric_def, "description") and metric_def.description and query in metric_def.description.lower():
                match_type = "description"
            else:
                continue

            description = getattr(metric_def, "description", "") or ""
            results.append({
                "platform": platform_name,
                "name": metric_name,
                "friendly_name": getattr(metric_def, "friendly_name", ""),
                "match_type": match_type,
                "description": description.split("\n")[0][:150],
            })

    if not results:
        return [TextContent(type="text", text=f"No metrics found matching '{query}'")]

    result = f"# Search Results for '{query}'\n\n"
    result += f"**Found {len(results)} metric(s)**\n\n"

    for item in results[:50]:  # Limit to 50 results
        result += f"## {item['name']} ({item['platform']})\n"
        result += f"- **Match Type:** {item['match_type']}\n"
        if item['friendly_name']:
            result += f"- **Friendly Name:** {item['friendly_name']}\n"
        if item['description']:
            result += f"- **Description:** {item['description']}...\n"
        result += "\n"

    if len(results) > 50:
        result += f"\n*Showing first 50 of {len(results)} results. Refine your search for more specific results.*\n"

    return [TextContent(type="text", text=result)]


async def handle_validate_metric_config(arguments: dict[str, Any]) -> list[TextContent]:
    """Validate a metric configuration."""
    config_toml = arguments["config_toml"]
    platform = arguments["platform"]

    try:
        # Parse TOML
        parsed = toml.loads(config_toml)

        # Basic validation
        errors = []
        warnings = []

        # Check for metrics section
        if "metrics" not in parsed:
            errors.append("Missing [metrics] section")
        else:
            metrics = parsed["metrics"]
            for metric_name, metric_def in metrics.items():
                # Check required fields
                if "select_expression" not in metric_def and "depends_on" not in metric_def:
                    errors.append(f"Metric '{metric_name}': Must have either 'select_expression' or 'depends_on'")

                if "select_expression" in metric_def and "data_source" not in metric_def:
                    errors.append(f"Metric '{metric_name}': 'data_source' is required when using 'select_expression'")

                # Check optional but recommended fields
                if "friendly_name" not in metric_def:
                    warnings.append(f"Metric '{metric_name}': Missing 'friendly_name' (recommended)")

                if "description" not in metric_def:
                    warnings.append(f"Metric '{metric_name}': Missing 'description' (recommended)")

                # Validate depends_on references if present
                if "depends_on" in metric_def:
                    if not isinstance(metric_def["depends_on"], list):
                        errors.append(f"Metric '{metric_name}': 'depends_on' must be a list")

        # Format results
        result = "# Validation Results\n\n"

        if not errors:
            result += "✅ **Configuration is valid!**\n\n"
        else:
            result += f"❌ **Found {len(errors)} error(s)**\n\n"
            result += "## Errors\n\n"
            for error in errors:
                result += f"- {error}\n"
            result += "\n"

        if warnings:
            result += f"⚠️ **Found {len(warnings)} warning(s)**\n\n"
            result += "## Warnings\n\n"
            for warning in warnings:
                result += f"- {warning}\n"
            result += "\n"

        if not errors and not warnings:
            result += "\nNo issues found. Configuration looks good!\n"

        result += "\n**Note:** This is a basic validation. For full validation including SQL dry-run, save the config to a file and run: `python3 .script/validate.py <file>`\n"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        return [TextContent(type="text", text=f"❌ **Validation Error**\n\nFailed to parse TOML: {str(e)}")]


async def handle_generate_metric_template(arguments: dict[str, Any]) -> list[TextContent]:
    """Generate a template for a new metric."""
    metric_name = arguments["metric_name"]
    data_source = arguments["data_source"]
    metric_type = arguments["metric_type"]

    template = f'[metrics.{metric_name}]\n'
    template += f'friendly_name = ""\n'
    template += f'description = """\n'
    template += f'    Add a detailed description of what this metric measures.\n'
    template += f'    Include information about:\n'
    template += f'    - What is being measured\n'
    template += f'    - How it\'s calculated\n'
    template += f'    - Any important caveats or notes\n'
    template += f'"""\n'

    if metric_type == "simple":
        template += f'data_source = "{data_source}"\n'
        template += f'select_expression = \'{{{{agg_sum("column_name")}}}}\'\n'
        template += f'category = ""\n'
        template += f'type = "scalar"\n'

    elif metric_type == "derived":
        template += f'depends_on = ["metric1", "metric2"]\n'
        template += f'# Derived metrics are computed from other metrics\n'
        template += f'# The computation is defined in the analysis configuration\n'

    elif metric_type == "custom":
        template += f'data_source = "{data_source}"\n'
        template += f'select_expression = \'-- Write your custom SQL here\'\n'
        template += f'category = ""\n'

    template += f'\n# Optional fields:\n'
    template += f'# bigger_is_better = true\n'
    template += f'# owner = ["email@mozilla.org"]\n'
    template += f'# level = "gold"  # gold, silver, bronze\n'

    result = f"# Metric Template: {metric_name}\n\n"
    result += f"Here's a template for your {metric_type} metric:\n\n"
    result += f"```toml\n{template}```\n\n"

    result += "## Next Steps\n\n"
    result += "1. Fill in the `friendly_name` and `description`\n"

    if metric_type == "simple":
        result += "2. Replace `column_name` with the actual column from your data source\n"
        result += "3. Choose an appropriate aggregation function:\n"
        result += "   - `agg_sum()` - Sum values (coalesces to 0)\n"
        result += "   - `agg_any()` - Logical OR for booleans\n"
        result += "   - `agg_histogram_mean()` - Mean of histogram\n"
        result += "   - Or use raw SQL: `COUNT(*)`, `AVG(column)`, etc.\n"
        result += "4. Set the `category` (e.g., 'search', 'performance', 'engagement')\n"

    elif metric_type == "derived":
        result += "2. Replace `metric1` and `metric2` with the actual metrics this depends on\n"
        result += "3. Define the calculation in your experiment or monitoring config\n"

    elif metric_type == "custom":
        result += "2. Write your custom SQL in the `select_expression`\n"
        result += "3. You can use Jinja2 templates and access data source columns\n"
        result += "4. Set the `category`\n"

    result += "5. Add optional fields as needed (owner, bigger_is_better, etc.)\n"
    result += "6. Validate your config using the `validate_metric_config` tool\n\n"
    result += "## Important: Where to add this metric\n\n"
    result += "This template is for **metric definitions** that go in the `definitions/` folder.\n"
    result += "These are reusable metrics that can be referenced in experiment configs.\n\n"
    result += "- **Add to definitions/**: `definitions/firefox_desktop.toml` (or your platform)\n"
    result += "- **Reference in experiments**: Use in `jetstream/your-experiment.toml` by adding the metric name to the [metrics] section\n"

    return [TextContent(type="text", text=result)]


async def handle_get_metric_sql(arguments: dict[str, Any]) -> list[TextContent]:
    """Generate SQL for a metric."""
    platform = arguments["platform"]
    metric_name = arguments["metric_name"]

    config = get_config_collection()

    try:
        metric_def = config.get_metric_definition(metric_name, platform)
    except Exception as e:
        return [TextContent(type="text", text=f"Metric '{metric_name}' not found in platform '{platform}': {e}")]

    result = f"# SQL for Metric: {metric_name}\n\n"

    if hasattr(metric_def, "select_expression") and metric_def.select_expression:
        result += "## Select Expression\n\n"
        result += f"```sql\n{metric_def.select_expression}\n```\n\n"

        if hasattr(metric_def, "data_source") and metric_def.data_source:
            try:
                ds_def = config.get_data_source_definition(metric_def.data_source, platform)
                result += "## Data Source\n\n"
                result += f"**Name:** {metric_def.data_source}\n\n"
                if hasattr(ds_def, "from_expression"):
                    result += f"**From:**\n```sql\n{ds_def.from_expression}\n```\n\n"
            except Exception:
                pass

        result += "## Full Query Example\n\n"
        result += "```sql\n"
        result += f"SELECT\n"
        result += f"  client_id,\n"
        result += f"  submission_date,\n"
        result += f"  {metric_def.select_expression} AS {metric_name}\n"
        result += f"FROM\n"

        if hasattr(metric_def, "data_source"):
            try:
                ds_def = config.get_data_source_definition(metric_def.data_source, platform)
                if hasattr(ds_def, "from_expression"):
                    result += f"  {ds_def.from_expression}\n"
            except Exception:
                result += f"  <data_source_table>\n"
        else:
            result += f"  <data_source_table>\n"

        result += f"WHERE\n"
        result += f"  submission_date >= '2025-01-01'\n"
        result += f"GROUP BY\n"
        result += f"  client_id,\n"
        result += f"  submission_date\n"
        result += "```\n\n"

    elif hasattr(metric_def, "depends_on") and metric_def.depends_on:
        result += "## Derived Metric\n\n"
        result += f"This metric is derived from: {', '.join(metric_def.depends_on)}\n\n"
        result += "The SQL is generated based on the computation defined in the experiment/monitoring config.\n\n"

    else:
        result += "No SQL expression found for this metric.\n"

    return [TextContent(type="text", text=result)]


async def handle_list_experiment_configs(arguments: dict[str, Any]) -> list[TextContent]:
    """List all experiment configuration files."""
    config_type = arguments["config_type"]

    # Get the repo path
    if _repo_path is None:
        repo_path = Path(__file__).parent.parent.parent.parent
    else:
        repo_path = _repo_path

    config_dir = repo_path / config_type

    if not config_dir.exists():
        return [TextContent(type="text", text=f"Directory '{config_type}' not found")]

    # List all .toml files (excluding defaults and definitions subdirectories)
    configs = []
    for config_file in config_dir.glob("*.toml"):
        if config_file.is_file():
            configs.append({
                "slug": config_file.stem,
                "path": str(config_file.relative_to(repo_path)),
            })

    result = f"# {config_type.title()} Configurations\n\n"
    result += f"**Total configs:** {len(configs)}\n\n"

    for config in sorted(configs, key=lambda x: x["slug"]):
        result += f"- `{config['slug']}`\n"

    return [TextContent(type="text", text=result)]


async def handle_get_experiment_config(arguments: dict[str, Any]) -> list[TextContent]:
    """Get the contents of an existing experiment configuration file."""
    config_type = arguments["config_type"]
    config_slug = arguments.get("config_slug") or arguments.get("experiment_slug")  # Support both parameter names

    # Get the repo path
    if _repo_path is None:
        repo_path = Path(__file__).parent.parent.parent.parent
    else:
        repo_path = _repo_path

    config_file = repo_path / config_type / f"{config_slug}.toml"

    if not config_file.exists():
        return [TextContent(type="text", text=f"Configuration file '{config_slug}.toml' not found in {config_type}/")]

    content = config_file.read_text()

    result = f"# Config: {config_slug}\n\n"
    result += f"**Path:** `{config_type}/{config_slug}.toml`\n\n"
    result += f"## Configuration\n\n```toml\n{content}```\n"

    return [TextContent(type="text", text=result)]


async def handle_create_experiment_config(arguments: dict[str, Any]) -> list[TextContent]:
    """Create a new experiment configuration file."""
    new_config_slug = arguments.get("new_config_slug") or arguments.get("new_experiment_slug")  # Support both parameter names
    config_type = arguments["config_type"]
    base_config_slug = arguments.get("base_config_slug")
    config_content = arguments.get("config_content")

    # Get the repo path
    if _repo_path is None:
        repo_path = Path(__file__).parent.parent.parent.parent
    else:
        repo_path = _repo_path

    new_config_file = repo_path / config_type / f"{new_config_slug}.toml"

    # Check if file already exists
    if new_config_file.exists():
        return [TextContent(type="text", text=f"Error: Configuration file '{new_config_slug}.toml' already exists in {config_type}/")]

    # Get content either from base config or from provided content
    if base_config_slug:
        base_config_file = repo_path / config_type / f"{base_config_slug}.toml"
        if not base_config_file.exists():
            return [TextContent(type="text", text=f"Error: Base configuration '{base_config_slug}.toml' not found in {config_type}/")]
        content = base_config_file.read_text()
    elif config_content:
        content = config_content
    else:
        return [TextContent(type="text", text="Error: Either 'base_config_slug' or 'config_content' must be provided")]

    # Write the new config file
    new_config_file.write_text(content)

    result = f"# Created Config: {new_config_slug}\n\n"
    result += f"**Path:** `{config_type}/{new_config_slug}.toml`\n\n"
    if base_config_slug:
        result += f"**Copied from:** `{base_config_slug}.toml`\n\n"
    result += f"## Content\n\n```toml\n{content}```\n\n"
    result += f"## Next Steps\n\n"
    result += f"1. Review and customize the configuration for your experiment\n"
    result += f"2. Update metric references to match your needs\n"
    result += f"3. Validate the configuration using `validate_metric_config`\n"
    result += f"4. Commit and push the configuration to the repository\n"

    return [TextContent(type="text", text=result)]


async def handle_generate_config_template(arguments: dict[str, Any]) -> list[TextContent]:
    """Generate a template for a new configuration."""
    config_type = arguments["config_type"]
    template_type = arguments["template_type"]
    platform = arguments["platform"]

    if config_type == "jetstream":
        return await handle_generate_jetstream_template(template_type, platform)
    elif config_type == "opmon":
        return await handle_generate_opmon_template(template_type, platform)
    elif config_type == "looker":
        return await handle_generate_looker_template(template_type, platform)
    else:
        return [TextContent(type="text", text=f"Unknown config type: {config_type}")]


async def handle_generate_jetstream_template(template_type: str, platform: str) -> list[TextContent]:
    """Generate a template for a jetstream experiment configuration."""
    templates = {
        "basic": f"""[experiment]
# Define experiment-level parameters
# enrollment_period = 7  # Duration in days
# reference_branch = "control"  # Control branch name

[metrics]
# Specify which metrics to compute for each analysis window
daily = []
weekly = []
28_day = []
overall = []

# Reference metrics from the {platform} platform definitions
# Example: weekly = ["active_hours", "uri_count"]
""",
        "with_segments": f"""[experiment]
segments = ["my_segment"]

# Define custom data source for segment
[segments.data_sources.my_data_source]
from_expression = \"\"\"(
  SELECT
    *
  FROM
    `moz-fx-data-shared-prod.telemetry.clients_daily`
)\"\"\"
window_start = 0
window_end = 28

# Define segment selection logic
[segments.my_segment]
select_expression = \"\"\"
  -- Replace with your segment selection logic
  -- Must return a boolean grouped by client_id
  CAST(MAX(column_name) > 0 AS BOOL)
\"\"\"
data_source = "my_data_source"

[metrics]
daily = []
weekly = []
28_day = []
overall = []
""",
        "with_custom_metrics": f"""[experiment]

[metrics]
daily = ["my_metric"]
weekly = ["my_metric"]
28_day = ["my_metric"]
overall = ["my_metric"]

# Define a custom metric
[metrics.my_metric]
select_expression = \"\"\"
  -- Replace with your metric calculation
  -- Example: COUNT(*)
  {{{{agg_sum("column_name")}}}}
\"\"\"
data_source = "main"  # Reference a data source from {platform} definitions
friendly_name = "My Custom Metric"
description = "Description of what this metric measures"
bigger_is_better = true

# Optional: Add statistics
[metrics.my_metric.statistics.binomial]
# Use for boolean/proportion metrics

# Or for continuous metrics:
# [metrics.my_metric.statistics.mean]
""",
        "with_custom_data_source": f"""[experiment]

# Define a custom data source
[data_sources.my_custom_source]
from_expression = \"\"\"
  -- Your custom SQL query or table reference
  `moz-fx-data-shared-prod.telemetry.events`
\"\"\"
experiments_column_type = "native"

[metrics]
daily = ["my_metric"]
weekly = ["my_metric"]

[metrics.my_metric]
select_expression = "COUNT(*)"
data_source = "my_custom_source"
friendly_name = "Event Count"
description = "Count of events from custom data source"
"""
    }

    template = templates.get(template_type, "")

    result = f"# Jetstream Experiment Configuration Template: {template_type}\n\n"
    result += f"**Platform:** {platform}\n\n"
    result += f"## Template\n\n```toml\n{template}```\n\n"
    result += f"## Key Configuration Sections\n\n"
    result += f"### [experiment]\n"
    result += f"- `segments`: List of user segments to analyze\n"
    result += f"- `enrollment_period`: Duration of enrollment in days\n"
    result += f"- `reference_branch`: Control branch name\n\n"
    result += f"### [metrics]\n"
    result += f"Specify metrics for each analysis window:\n"
    result += f"- `daily`: Metrics computed daily\n"
    result += f"- `weekly`: Metrics computed weekly\n"
    result += f"- `28_day`: Metrics computed over 28 days\n"
    result += f"- `overall`: Metrics computed over entire experiment\n\n"
    result += f"### Custom Metrics\n"
    result += f"Define with `[metrics.metric_name]` and include:\n"
    result += f"- `select_expression`: SQL aggregation clause\n"
    result += f"- `data_source`: Reference to data source\n"
    result += f"- `friendly_name`: Display name\n"
    result += f"- `description`: What the metric measures\n\n"
    result += f"## Documentation\n\n"
    result += f"For more details, see: https://experimenter.info/deep-dives/jetstream/configuration\n"

    return [TextContent(type="text", text=result)]


async def handle_generate_opmon_template(template_type: str, platform: str) -> list[TextContent]:
    """Generate a template for an opmon operational monitoring configuration."""
    templates = {
        "basic": f"""[project]
name = "My Monitoring Project"
platform = "{platform}"
xaxis = "submission_date"
start_date = "2025-01-01"
skip_default_metrics = false

# Metrics to monitor
metrics = [
    "active_hours",
    "uri_count",
]

[project.population]
# Monitor the entire population
data_source = "main"
monitor_entire_population = true

# Or monitor specific criteria
# [project.population.criteria]
# channel = ["release"]

[metrics.active_hours.statistics]
sum = {{}}

[metrics.uri_count.statistics]
sum = {{}}
""",
        "with_dimensions": f"""[project]
name = "My Monitoring Project with Dimensions"
platform = "{platform}"
xaxis = "submission_date"
start_date = "2025-01-01"
skip_default_metrics = false

# Dimensions to break down the metrics
dimensions = [
    "country",
    "channel",
]

metrics = [
    "active_hours",
]

[project.population]
data_source = "main"
monitor_entire_population = true

# Define custom metrics if needed
[metrics.active_hours]
data_source = "main"
select_expression = "{{{{agg_sum('active_hours_sum')}}}}"
type = "scalar"
friendly_name = "Active Hours"
description = "Total active hours"

[metrics.active_hours.statistics]
sum = {{}}

# Define custom data sources if needed
[data_sources.main]
from_expression = "`moz-fx-data-shared-prod.telemetry.clients_daily`"
""",
    }

    template = templates.get(template_type, templates["basic"])

    result = f"# OpMon Configuration Template: {template_type}\n\n"
    result += f"**Platform:** {platform}\n\n"
    result += f"## Template\n\n```toml\n{template}```\n\n"
    result += f"## Key Configuration Sections\n\n"
    result += f"### [project]\n"
    result += f"- `name`: Display name for the monitoring project\n"
    result += f"- `platform`: Platform being monitored (e.g., 'firefox_desktop', 'fenix')\n"
    result += f"- `xaxis`: Time dimension (typically 'submission_date')\n"
    result += f"- `start_date`: Start date for monitoring\n"
    result += f"- `dimensions`: Optional dimensions to break down metrics by\n\n"
    result += f"### [project.population]\n"
    result += f"- `data_source`: Data source for population definition\n"
    result += f"- `monitor_entire_population`: Set to true to monitor all users\n"
    result += f"- `criteria`: Optional filters for population\n\n"
    result += f"### [metrics]\n"
    result += f"List metrics to monitor and define their statistics\n\n"
    result += f"## Documentation\n\n"
    result += f"For more details, see: https://docs.telemetry.mozilla.org/cookbooks/operational_monitoring.html\n"

    return [TextContent(type="text", text=result)]


async def handle_generate_looker_template(template_type: str, platform: str) -> list[TextContent]:
    """Generate a template for a looker dashboard configuration."""
    template = f"""# Looker configurations are typically stored in looker/definitions/

[data_sources.'*']
# Enable all columns as dimensions for Looker
columns_as_dimensions = true

# Example custom metric for Looker
[metrics.my_metric]
data_source = "my_data_source"
select_expression = "COUNT(*)"
type = "scalar"
friendly_name = "My Metric"
description = "Description of the metric"

[data_sources.my_data_source]
from_expression = "`moz-fx-data-shared-prod.{platform}.table_name`"
submission_date_column = "submission_date"
"""

    result = f"# Looker Configuration Template\n\n"
    result += f"**Platform:** {platform}\n\n"
    result += f"## Template\n\n```toml\n{template}```\n\n"
    result += f"## Key Configuration Notes\n\n"
    result += f"- Looker configs are stored in `looker/definitions/` directory\n"
    result += f"- Use `columns_as_dimensions = true` to enable all columns as Looker dimensions\n"
    result += f"- Define custom metrics and data sources as needed\n\n"
    result += f"## Documentation\n\n"
    result += f"For more details, see metric-hub documentation\n"

    return [TextContent(type="text", text=result)]


async def handle_list_segments(arguments: dict[str, Any]) -> list[TextContent]:
    """List all segments for a platform."""
    platform = arguments["platform"]

    config = get_config_collection()

    segments = config.get_segments_for_app(platform)

    if not segments:
        return [TextContent(type="text", text=f"No segments found for platform '{platform}'")]

    result = f"# Segments for {platform}\n\n"
    result += f"**Total segments:** {len(segments)}\n\n"

    for segment in sorted(segments, key=lambda x: x.name):
        result += f"## {segment.name}\n"

        if segment.friendly_name:
            result += f"**Friendly Name:** {segment.friendly_name}\n\n"

        if segment.description:
            result += f"**Description:** {segment.description}\n\n"

        result += f"**Data Source:** {segment.data_source.name}\n\n"

        result += "\n"

    return [TextContent(type="text", text=result)]


async def handle_get_segment(arguments: dict[str, Any]) -> list[TextContent]:
    """Get detailed information about a segment."""
    platform = arguments["platform"]
    segment_name = arguments["segment_name"]

    config = get_config_collection()

    segment = config.get_segment_definition(segment_name, platform)

    if not segment:
        return [TextContent(type="text", text=f"Segment '{segment_name}' not found in platform '{platform}'")]

    result = f"# Segment: {segment_name}\n\n"
    result += f"**Platform:** {platform}\n\n"

    if segment.friendly_name:
        result += f"**Friendly Name:** {segment.friendly_name}\n\n"

    if segment.description:
        result += f"## Description\n\n{segment.description}\n\n"

    result += f"## Configuration\n\n"
    result += f"**Data Source:** {segment.data_source.name}\n\n"

    result += f"## Select Expression\n\n```sql\n{segment.select_expression}\n```\n\n"

    result += f"## Usage\n\n"
    result += f"To use this segment in an experiment config, add it to the `segments` list:\n\n"
    result += f"```toml\n[experiment]\nsegments = [\"{segment_name}\"]\n```\n\n"
    result += f"The analysis will then be performed separately for users in this segment.\n"

    return [TextContent(type="text", text=result)]


async def handle_list_experiments(arguments: dict[str, Any]) -> list[TextContent]:
    """List experiments and rollouts from Experimenter."""
    status_filter = arguments.get("status")
    app_name_filter = arguments.get("app_name")
    is_rollout_filter = arguments.get("is_rollout")

    experiments = fetch_experiments_from_experimenter()

    if not experiments:
        return [TextContent(type="text", text="No experiments found or error fetching from Experimenter")]

    # Apply filters
    filtered = []
    for exp in experiments:
        # Determine status
        exp_status = "Live"
        if exp.get("endDate"):
            from datetime import datetime
            try:
                end_date = datetime.strptime(exp["endDate"], "%Y-%m-%d")
                if end_date < datetime.now():
                    exp_status = "Complete"
            except Exception:
                pass

        # Status filter
        if status_filter and exp_status != status_filter:
            continue

        # App name filter
        app_name = exp.get("appName", "firefox_desktop")
        if app_name_filter and app_name != app_name_filter:
            continue

        # Rollout filter
        branches = exp.get("branches", [])
        is_rollout = exp.get("isRollout", len(branches) == 1)
        if is_rollout_filter is not None and is_rollout != is_rollout_filter:
            continue

        # Only show launched experiments (with start date)
        if exp.get("startDate"):
            filtered.append({
                "slug": exp.get("slug", ""),
                "name": exp.get("userFacingName", ""),
                "status": exp_status,
                "app_name": app_name,
                "is_rollout": is_rollout,
                "start_date": exp.get("startDate", ""),
                "end_date": exp.get("endDate", ""),
                "channel": exp.get("channel", ""),
            })

    result = "# Experiments and Rollouts from Experimenter\n\n"
    result += f"**Total found:** {len(filtered)}\n\n"

    if not filtered:
        result += "No experiments match the specified filters.\n"
        return [TextContent(type="text", text=result)]

    # Group by status
    by_status: dict[str, list] = {"Live": [], "Complete": []}
    for exp in filtered:
        by_status[exp["status"]].append(exp)

    for status in ["Live", "Complete"]:
        if by_status[status]:
            result += f"## {status}\n\n"
            for exp in sorted(by_status[status], key=lambda x: x["slug"]):
                exp_type = "🚀 Rollout" if exp["is_rollout"] else "🧪 Experiment"
                result += f"### {exp_type}: {exp['slug']}\n"
                if exp["name"]:
                    result += f"**Name:** {exp['name']}\n\n"
                result += f"- **App:** {exp['app_name']}\n"
                if exp["channel"]:
                    result += f"- **Channel:** {exp['channel']}\n"
                result += f"- **Start Date:** {exp['start_date']}\n"
                if exp["end_date"]:
                    result += f"- **End Date:** {exp['end_date']}\n"
                result += "\n"

    return [TextContent(type="text", text=result)]


async def handle_get_experiment_from_experimenter(arguments: dict[str, Any]) -> list[TextContent]:
    """Get detailed information about a specific experiment from Experimenter."""
    slug = arguments["slug"]

    experiments = fetch_experiments_from_experimenter()

    if not experiments:
        return [TextContent(type="text", text="Error fetching experiments from Experimenter")]

    # Find the experiment
    experiment = None
    for exp in experiments:
        if exp.get("slug") == slug:
            experiment = exp
            break

    if not experiment:
        return [TextContent(type="text", text=f"Experiment '{slug}' not found in Experimenter")]

    # Determine status
    status = "Live"
    if experiment.get("endDate"):
        from datetime import datetime
        try:
            end_date = datetime.strptime(experiment["endDate"], "%Y-%m-%d")
            if end_date < datetime.now():
                status = "Complete"
        except Exception:
            pass

    branches = experiment.get("branches", [])
    is_rollout = experiment.get("isRollout", len(branches) == 1)

    result = f"# {'Rollout' if is_rollout else 'Experiment'}: {slug}\n\n"

    if experiment.get("userFacingName"):
        result += f"**Name:** {experiment['userFacingName']}\n\n"

    result += f"**Status:** {status}\n\n"

    result += f"## Details\n\n"
    result += f"- **App Name:** {experiment.get('appName', 'firefox_desktop')}\n"
    result += f"- **App ID:** {experiment.get('appId', 'firefox-desktop')}\n"

    if experiment.get("channel"):
        result += f"- **Channel:** {experiment['channel']}\n"

    result += f"- **Start Date:** {experiment.get('startDate', 'Not set')}\n"
    result += f"- **End Date:** {experiment.get('endDate', 'Not set')}\n"

    if experiment.get("referenceBranch"):
        result += f"- **Reference Branch:** {experiment['referenceBranch']}\n"

    result += f"\n## Branches\n\n"
    for branch in branches:
        result += f"### {branch.get('slug', 'unknown')}\n"
        result += f"- **Ratio:** {branch.get('ratio', 1)}\n\n"

    # Check if there's a config in the repo
    has_jetstream_config = False
    has_opmon_config = False

    if _repo_path is None:
        repo_path = Path(__file__).parent.parent.parent.parent
    else:
        repo_path = _repo_path

    jetstream_file = repo_path / "jetstream" / f"{slug}.toml"
    opmon_file = repo_path / "opmon" / f"{slug}.toml"

    if jetstream_file.exists():
        has_jetstream_config = True
    if opmon_file.exists():
        has_opmon_config = True

    if has_jetstream_config or has_opmon_config:
        result += f"## Configurations in Repo\n\n"
        if has_jetstream_config:
            result += f"- ✅ Jetstream config: `jetstream/{slug}.toml`\n"
        if has_opmon_config:
            result += f"- ✅ OpMon config: `opmon/{slug}.toml`\n"
        result += "\n"

    result += f"## API Data\n\n"
    result += f"View full experiment details at:\n"
    result += f"https://experimenter.services.mozilla.com/nimbus/{slug}/summary\n"

    return [TextContent(type="text", text=result)]


async def main() -> None:
    """Run the MCP server via stdio (local mode)."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


async def run_sse_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Run the MCP server via HTTP SSE (remote mode).

    This allows the server to be deployed remotely and accessed over HTTP.

    Args:
        host: Host to bind to (default: 0.0.0.0 for all interfaces)
        port: Port to listen on (default: 8080)
    """
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import Response
    import uvicorn

    async def handle_sse(request):
        async with SseServerTransport("/messages") as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )
            return Response()

    async def handle_messages(request):
        async with SseServerTransport("/messages") as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )
            return Response()

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
        ]
    )

    config = uvicorn.Config(
        starlette_app,
        host=host,
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


def cli() -> None:
    """CLI entry point for local stdio mode."""
    import asyncio
    asyncio.run(main())


def cli_http() -> None:
    """CLI entry point for remote HTTP/SSE mode."""
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="Run Metric Hub MCP Server in HTTP/SSE mode"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)"
    )

    args = parser.parse_args()

    logger.info(f"Starting Metric Hub MCP Server on {args.host}:{args.port}")
    asyncio.run(run_sse_server(host=args.host, port=args.port))


if __name__ == "__main__":
    cli()
