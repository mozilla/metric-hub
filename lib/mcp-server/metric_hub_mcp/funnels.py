"""Handlers for funnel building and Glean event discovery."""

import logging
from typing import Any

import asyncio

import requests
from mcp.types import TextContent

logger = logging.getLogger(__name__)

GLEAN_DICTIONARY_BASE = "https://probeinfo.telemetry.mozilla.org"

# metric-hub platform slug -> BigQuery dataset name
PLATFORM_TO_BQ_DATASET: dict[str, str] = {
    "firefox_desktop": "firefox_desktop",
    "fenix": "org_mozilla_firefox",
    "firefox_ios": "firefox_ios",
    "focus_android": "org_mozilla_focus",
    "focus_ios": "org_mozilla_focus_ios",
    "klar_android": "org_mozilla_klar",
    "klar_ios": "org_mozilla_focus_ios",
}


def _fetch_glean_metrics_sync(product: str) -> dict:
    probe_product = product.replace("_", "-")
    url = f"{GLEAN_DICTIONARY_BASE}/glean/{probe_product}/metrics"
    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": "metric-hub-mcp/0.1.0"})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch Glean metrics for {product}: {e}")
        return {}


async def _fetch_glean_metrics(product: str) -> dict:
    """Fetch all metrics for a product from the Glean probe scraper."""
    return await asyncio.to_thread(_fetch_glean_metrics_sync, product)


LOOKER_BASE = "https://mozilla.cloud.looker.com"


def _extra_filter_field(extra_key: str) -> str:
    """Map an extra key prefix to the correct Looker filter field suffix."""
    if extra_key.startswith("booleans."):
        return "extra_bool_filter"
    if extra_key.startswith("quantities."):
        return "extra_number_filter"
    return "extra_string_filter"


def _build_looker_url(
    steps: list[dict],
    product: str = "firefox_desktop",
    filters: dict | None = None,
) -> str:
    """Build a Looker event_funnel explore URL pre-populated with funnel step filters.

    Each step may include an optional ``extra`` dict with:
      - ``key``: extra field path, e.g. ``strings.action``, ``booleans.checked``, ``quantities.duration_ms``
      - ``value``: the filter value
    """
    from urllib.parse import urlencode

    if len(steps) > 4:
        steps = steps[:4]

    params: list[tuple[str, str]] = []
    for i, step in enumerate(steps, 1):
        params.append((f"f[event_funnel.step_{i}_event]", step["event_name"]))
        params.append((f"f[event_funnel.step_{i}_category]", step["event_category"]))
        if extra := step.get("extra"):
            key = extra.get("key", "")
            value = extra.get("value", "")
            if key and value:
                params.append((f"f[event_funnel.step_{i}_extra_name_filter]", key))
                filter_field = _extra_filter_field(key)
                params.append((f"f[event_funnel.step_{i}_{filter_field}]", str(value)))

    if filters:
        if filters.get("country"):
            countries = filters["country"] if isinstance(filters["country"], list) else [filters["country"]]
            params.append(("f[event_funnel.country]", ",".join(countries)))
        if filters.get("channel"):
            params.append(("f[event_funnel.channel]", filters["channel"]))
        if filters.get("os"):
            params.append(("f[event_funnel.os]", filters["os"]))

    fields = ",".join(f"event_funnel.step_{i}_clients" for i in range(1, len(steps) + 1))
    params.append(("fields", fields))
    params.append(("toggle", "vis,vse"))

    return f"{LOOKER_BASE}/explore/{product}/event_funnel?{urlencode(params)}"



async def handle_search_glean_events(arguments: dict[str, Any]) -> list[TextContent]:
    """Search Glean events by name, category, description, or tag."""
    product = arguments.get("product", "firefox_desktop")
    query = arguments["query"].lower()

    all_metrics = await _fetch_glean_metrics(product)
    if not all_metrics:
        return [TextContent(type="text", text=f"Failed to fetch metrics for '{product}' from Glean.")]

    matches = []
    for metric_name, metric_data in all_metrics.items():
        if metric_data.get("type") != "event":
            continue

        description = metric_data.get("description", "")
        tags = " ".join(metric_data.get("tags", []))

        if query in metric_name.lower() or query in description.lower() or query in tags.lower():
            parts = metric_name.rsplit(".", 1)
            category = parts[0] if len(parts) > 1 else ""
            event_name = parts[1] if len(parts) > 1 else metric_name

            matches.append({
                "metric_name": metric_name,
                "category": category,
                "event_name": event_name,
                "description": description,
                "extra_keys": metric_data.get("extra_keys", {}),
                "tags": metric_data.get("tags", []),
            })

    if not matches:
        return [TextContent(type="text", text=f"No events found matching '{query}' in {product}.")]

    result = f"# Glean Events matching '{query}' ({product})\n\n"
    result += f"**Found {len(matches)} event(s)**\n\n"

    by_category: dict[str, list] = {}
    for m in matches:
        by_category.setdefault(m["category"], []).append(m)

    for category in sorted(by_category.keys()):
        result += f"## {category}\n\n"
        for event in sorted(by_category[category], key=lambda x: x["event_name"]):
            result += f"### `{event['metric_name']}`\n"
            result += f"- **event_category:** `{event['category']}`\n"
            result += f"- **event_name:** `{event['event_name']}`\n"
            if event["description"]:
                result += f"- **Description:** {event['description']}\n"
            if event["extra_keys"]:
                keys = ", ".join(f"`{k}`" for k in event["extra_keys"].keys())
                result += f"- **Extra keys:** {keys}\n"
            if event["tags"]:
                result += f"- **Tags:** {', '.join(event['tags'])}\n"
            result += "\n"

    return [TextContent(type="text", text=result)]


async def handle_get_glean_event(arguments: dict[str, Any]) -> list[TextContent]:
    """Get full details for a specific Glean event including BQ location."""
    product = arguments.get("product", "firefox_desktop")
    metric_name = arguments["metric_name"]

    all_metrics = await _fetch_glean_metrics(product)
    if not all_metrics:
        return [TextContent(type="text", text=f"Failed to fetch metrics for '{product}' from Glean.")]

    if metric_name not in all_metrics:
        return [TextContent(type="text", text=f"Event `{metric_name}` not found in {product}.")]

    metric_data = all_metrics[metric_name]
    if metric_data.get("type") != "event":
        return [TextContent(
            type="text",
            text=f"`{metric_name}` is type '{metric_data.get('type')}', not 'event'.",
        )]

    parts = metric_name.rsplit(".", 1)
    category = parts[0] if len(parts) > 1 else ""
    event_name = parts[1] if len(parts) > 1 else metric_name
    bq_dataset = PLATFORM_TO_BQ_DATASET.get(product, product)

    result = f"# Glean Event: `{metric_name}`\n\n"
    result += f"**Product:** {product}\n\n"
    result += "## BigQuery\n\n"
    result += f"- **Table:** `mozdata.{bq_dataset}.events_stream`\n"
    result += f"- **Filter:** `event_category = '{category}' AND event_name = '{event_name}'`\n\n"
    result += "## Details\n\n"
    result += f"- **event_category:** `{category}`\n"
    result += f"- **event_name:** `{event_name}`\n"

    if metric_data.get("description"):
        result += f"\n**Description:** {metric_data['description']}\n"

    if metric_data.get("extra_keys"):
        result += "\n## Extra Keys\n\n"
        for key, key_data in metric_data["extra_keys"].items():
            key_desc = key_data.get("description", "") if isinstance(key_data, dict) else str(key_data)
            result += f"- **`{key}`**: {key_desc}\n"

    if metric_data.get("tags"):
        result += f"\n**Tags:** {', '.join(metric_data['tags'])}\n"

    return [TextContent(type="text", text=result)]


async def handle_list_glean_event_categories(arguments: dict[str, Any]) -> list[TextContent]:
    """List all event categories for a product."""
    product = arguments.get("product", "firefox_desktop")

    all_metrics = await _fetch_glean_metrics(product)
    if not all_metrics:
        return [TextContent(type="text", text=f"Failed to fetch metrics for '{product}' from Glean.")]

    categories: dict[str, int] = {}
    for metric_name, metric_data in all_metrics.items():
        if metric_data.get("type") != "event":
            continue
        parts = metric_name.rsplit(".", 1)
        if len(parts) > 1:
            cat = parts[0]
            categories[cat] = categories.get(cat, 0) + 1

    if not categories:
        return [TextContent(type="text", text=f"No event categories found for '{product}'.")]

    result = f"# Glean Event Categories ({product})\n\n"
    result += f"**Total categories:** {len(categories)}\n\n"
    for category in sorted(categories.keys()):
        result += f"- **{category}** ({categories[category]} event(s))\n"
    result += "\nUse `search_glean_events` with a category name to see events within it.\n"

    return [TextContent(type="text", text=result)]


async def handle_build_funnel_url(arguments: dict[str, Any]) -> list[TextContent]:
    """Build a Looker event_funnel explore URL, validating events against the Glean dictionary."""
    product = arguments.get("product", "firefox_desktop")
    steps: list[dict] = arguments["steps"]
    filters: dict = arguments.get("filters", {})

    for i, step in enumerate(steps, 1):
        if "event_category" not in step or "event_name" not in step:
            return [TextContent(
                type="text",
                text=f"Step {i} is missing 'event_category' or 'event_name'.",
            )]
        step.setdefault("label", f"step_{i}")

    if len(steps) > 4:
        return [TextContent(type="text", text="The event_funnel explore supports up to 4 steps.")]

    # Validate events against Glean
    all_metrics = await _fetch_glean_metrics(product)
    validation_notes: list[str] = []
    if all_metrics:
        for step in steps:
            metric_name = f"{step['event_category']}.{step['event_name']}"
            if metric_name not in all_metrics:
                validation_notes.append(f"⚠️  `{metric_name}` not found in Glean for {product}")
            elif all_metrics[metric_name].get("type") != "event":
                actual_type = all_metrics[metric_name].get("type")
                validation_notes.append(
                    f"⚠️  `{metric_name}` exists but is type '{actual_type}', not 'event'"
                )

    url = _build_looker_url(steps, product=product, filters=filters)

    result = "# Funnel Explore\n\n"
    result += f"**Product:** {product}  \n"
    result += f"**Steps:** {len(steps)}\n\n"

    if validation_notes:
        result += "## Validation Warnings\n\n"
        for note in validation_notes:
            result += f"{note}\n"
        result += "\n"

    result += "## Funnel Steps\n\n"
    for i, step in enumerate(steps, 1):
        desc = step.get("description", "")
        result += f"{i}. **{step['label']}** — `{step['event_category']}.{step['event_name']}`"
        if desc:
            result += f" — {desc}"
        result += "\n"

    if filters:
        result += "\n## Filters\n\n"
        for k, v in filters.items():
            result += f"- **{k}:** {v}\n"

    result += f"\n## Looker Explore\n\nOpen with: `open \"{url}\"`\n"

    return [TextContent(type="text", text=result)]

