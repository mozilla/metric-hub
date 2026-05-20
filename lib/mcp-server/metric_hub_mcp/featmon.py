"""Handlers for Nimbus feature monitoring (featmon) configs."""

import logging
from typing import Any

from mcp.types import TextContent

from .config import get_config_collection

logger = logging.getLogger(__name__)


async def handle_list_monitored_features(arguments: dict[str, Any]) -> list[TextContent]:
    """List all Nimbus features that have feature monitoring configs."""
    platform_filter = arguments.get("platform")
    config = get_config_collection()

    result = "# Monitored Nimbus Features\n\n"
    found = False

    for app_config in config.featmon_configs:
        if platform_filter and app_config.slug != platform_filter:
            continue

        found = True
        result += f"## {app_config.slug}\n\n"
        for feat_key, feat in app_config.spec.features.items():
            nimbus_slug = feat.nimbus_slug()
            sources = list(feat.metrics_by_source.keys())
            result += f"### {nimbus_slug}\n"
            if nimbus_slug != feat_key:
                result += f"- TOML key: `{feat_key}`\n"
            result += f"- Sources: {', '.join(sources) if sources else 'none'}\n"
            total_metrics = sum(
                sum(len(metrics) for metrics in source_metrics.values())
                for source_metrics in feat.metrics_by_source.values()
            )
            result += f"- Metrics tracked: {total_metrics}\n\n"

    if not found:
        if platform_filter:
            result += f"No monitored features found for platform '{platform_filter}'.\n"
            result += (
                "Use list_monitored_features without a platform filter to see all platforms.\n"
            )
        else:
            result += "No featmon configs found.\n"

    return [TextContent(type="text", text=result)]


async def handle_get_monitored_feature(arguments: dict[str, Any]) -> list[TextContent]:
    """Get detailed featmon config for a specific Nimbus feature."""
    feature_slug = arguments["feature_slug"]
    platform_filter = arguments.get("platform")
    config = get_config_collection()

    for app_config in config.featmon_configs:
        if platform_filter and app_config.slug != platform_filter:
            continue

        for feat_key, feat in app_config.spec.features.items():
            if feat.nimbus_slug() != feature_slug and feat_key != feature_slug:
                continue

            result = f"# Feature: {feat.nimbus_slug()}\n"
            result += f"**Platform:** {app_config.slug}\n"
            if feat.slug is not None:
                result += f"**TOML key:** `{feat_key}` (slug overridden to `{feat.slug}`)\n"
            result += "\n"

            result += "## Data Sources\n\n"
            for source_name, source in app_config.spec.data_sources.items():
                result += f"### {source_name}\n"
                result += f"- Table: `{source.table_name}`\n"
                result += f"- Type: `{source.type}`\n"
                result += f"- Analysis unit: `{source.analysis_unit_id}`\n"
                if source.dimensions:
                    result += f"- Dimensions: {', '.join(source.dimensions.keys())}\n"
                result += "\n"

            result += "## Metrics by Source\n\n"
            if not feat.metrics_by_source:
                result += "No metrics configured.\n"
            else:
                for source_name, source_metrics in feat.metrics_by_source.items():
                    result += f"### {source_name}\n"
                    for data_type, metrics in source_metrics.items():
                        if data_type == "event":
                            for category, category_metrics in metrics.items():
                                for metric_name in category_metrics:
                                    result += (
                                        f"- `{category}_{metric_name}`"
                                        f" (event: {category}.{metric_name})\n"
                                    )
                        else:
                            for metric_name in metrics:
                                result += f"- `{metric_name}` ({data_type})\n"
                    result += "\n"

            return [TextContent(type="text", text=result)]

    msg = f"Feature '{feature_slug}' not found."
    if not platform_filter:
        msg += " Use list_monitored_features to see all available features."
    return [TextContent(type="text", text=msg)]
