"""Handlers for metrics, data sources, and segments."""

import logging
from typing import Any

from mcp.types import TextContent

from .config import get_config_collection

logger = logging.getLogger(__name__)


async def handle_list_platforms() -> list[TextContent]:
    """List all available platforms."""
    config = get_config_collection()

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
    except Exception:
        return [TextContent(type="text", text=f"Platform '{platform}' not found. Use list_platforms to see available platforms.")]

    if not definition_config or not definition_config.metrics or not definition_config.metrics.definitions:
        return [TextContent(type="text", text=f"No metrics found for platform '{platform}'")]

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
            if query in metric_name.lower():
                match_type = "name"
            elif hasattr(metric_def, "friendly_name") and metric_def.friendly_name and query in metric_def.friendly_name.lower():
                match_type = "friendly_name"
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

    for item in results[:50]:
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


async def handle_generate_metric_template(arguments: dict[str, Any]) -> list[TextContent]:
    """Generate a template for a new metric."""
    metric_name = arguments["metric_name"]
    data_source = arguments["data_source"]
    metric_type = arguments["metric_type"]

    template = f'[metrics.{metric_name}]\n'
    template += 'friendly_name = ""\n'
    template += 'description = """\n'
    template += '    Add a detailed description of what this metric measures.\n'
    template += '    Include information about:\n'
    template += '    - What is being measured\n'
    template += '    - How it\'s calculated\n'
    template += '    - Any important caveats or notes\n'
    template += '"""\n'

    if metric_type == "simple":
        template += f'data_source = "{data_source}"\n'
        template += 'select_expression = \'{{agg_sum("column_name")}}\'\n'
        template += 'category = ""\n'
        template += 'type = "scalar"\n'
    elif metric_type == "derived":
        template += 'depends_on = ["metric1", "metric2"]\n'
        template += '# Derived metrics are computed from other metrics\n'
        template += '# The computation is defined in the analysis configuration\n'
    elif metric_type == "custom":
        template += f'data_source = "{data_source}"\n'
        template += 'select_expression = \'-- Write your custom SQL here\'\n'
        template += 'category = ""\n'

    template += '\n# Optional fields:\n'
    template += '# bigger_is_better = true\n'
    template += '# owner = ["email@mozilla.org"]\n'
    template += '# level = "gold"  # gold, silver, bronze\n'

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

        result += "## Full Query Example\n\n```sql\n"
        result += "SELECT\n"
        result += "  client_id,\n"
        result += "  submission_date,\n"
        result += f"  {metric_def.select_expression} AS {metric_name}\n"
        result += "FROM\n"

        if hasattr(metric_def, "data_source"):
            try:
                ds_def = config.get_data_source_definition(metric_def.data_source, platform)
                if hasattr(ds_def, "from_expression"):
                    result += f"  {ds_def.from_expression}\n"
            except Exception:
                result += "  <data_source_table>\n"
        else:
            result += "  <data_source_table>\n"

        result += "WHERE\n"
        result += "  submission_date >= '2025-01-01'\n"
        result += "GROUP BY\n"
        result += "  client_id,\n"
        result += "  submission_date\n"
        result += "```\n\n"

    elif hasattr(metric_def, "depends_on") and metric_def.depends_on:
        result += "## Derived Metric\n\n"
        result += f"This metric is derived from: {', '.join(metric_def.depends_on)}\n\n"
        result += "The SQL is generated based on the computation defined in the experiment/monitoring config.\n\n"

    else:
        result += "No SQL expression found for this metric.\n"

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

    result += "## Configuration\n\n"
    result += f"**Data Source:** {segment.data_source.name}\n\n"
    result += f"## Select Expression\n\n```sql\n{segment.select_expression}\n```\n\n"
    result += "## Usage\n\n"
    result += "To use this segment in an experiment config, add it to the `segments` list:\n\n"
    result += f"```toml\n[experiment]\nsegments = [\"{segment_name}\"]\n```\n\n"
    result += "The analysis will then be performed separately for users in this segment.\n"

    return [TextContent(type="text", text=result)]
