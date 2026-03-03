"""Handlers for experiments: Experimenter API and jetstream/opmon/looker config files."""

import logging
from datetime import datetime
from typing import Any

from mcp.types import TextContent

from .config import get_repo_path
from .experimenter import fetch_experiments

logger = logging.getLogger(__name__)


# --- Experimenter API ---

def _parse_status(exp: dict[str, Any]) -> str:
    """Determine experiment status from end date."""
    if exp.get("endDate"):
        try:
            if datetime.strptime(exp["endDate"], "%Y-%m-%d") < datetime.now():
                return "Complete"
        except Exception:
            pass
    return "Live"


async def handle_list_experiments(arguments: dict[str, Any]) -> list[TextContent]:
    """List experiments and rollouts from Experimenter."""
    status_filter = arguments.get("status")
    app_name_filter = arguments.get("app_name")
    is_rollout_filter = arguments.get("is_rollout")

    experiments = fetch_experiments()

    if not experiments:
        return [TextContent(type="text", text="No experiments found or error fetching from Experimenter")]

    filtered = []
    for exp in experiments:
        if not exp.get("startDate"):
            continue

        exp_status = _parse_status(exp)
        if status_filter and exp_status != status_filter:
            continue

        app_name = exp.get("appName", "firefox_desktop")
        if app_name_filter and app_name != app_name_filter:
            continue

        branches = exp.get("branches", [])
        is_rollout = exp.get("isRollout", len(branches) == 1)
        if is_rollout_filter is not None and is_rollout != is_rollout_filter:
            continue

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


async def handle_get_experiment(arguments: dict[str, Any]) -> list[TextContent]:
    """Get detailed information about a specific experiment from Experimenter."""
    slug = arguments["slug"]

    experiments = fetch_experiments()
    if not experiments:
        return [TextContent(type="text", text="Error fetching experiments from Experimenter")]

    experiment = next((e for e in experiments if e.get("slug") == slug), None)
    if not experiment:
        return [TextContent(type="text", text=f"Experiment '{slug}' not found in Experimenter")]

    status = _parse_status(experiment)
    branches = experiment.get("branches", [])
    is_rollout = experiment.get("isRollout", len(branches) == 1)

    result = f"# {'Rollout' if is_rollout else 'Experiment'}: {slug}\n\n"

    if experiment.get("userFacingName"):
        result += f"**Name:** {experiment['userFacingName']}\n\n"

    result += f"**Status:** {status}\n\n"
    result += "## Details\n\n"
    result += f"- **App Name:** {experiment.get('appName', 'firefox_desktop')}\n"
    result += f"- **App ID:** {experiment.get('appId', 'firefox-desktop')}\n"

    if experiment.get("channel"):
        result += f"- **Channel:** {experiment['channel']}\n"

    result += f"- **Start Date:** {experiment.get('startDate', 'Not set')}\n"
    result += f"- **End Date:** {experiment.get('endDate', 'Not set')}\n"

    if experiment.get("referenceBranch"):
        result += f"- **Reference Branch:** {experiment['referenceBranch']}\n"

    result += "\n## Branches\n\n"
    for branch in branches:
        result += f"### {branch.get('slug', 'unknown')}\n"
        result += f"- **Ratio:** {branch.get('ratio', 1)}\n\n"

    repo_path = get_repo_path()
    jetstream_exists = (repo_path / "jetstream" / f"{slug}.toml").exists()
    opmon_exists = (repo_path / "opmon" / f"{slug}.toml").exists()

    if jetstream_exists or opmon_exists:
        result += "## Configurations in Repo\n\n"
        if jetstream_exists:
            result += f"- ✅ Jetstream config: `jetstream/{slug}.toml`\n"
        if opmon_exists:
            result += f"- ✅ OpMon config: `opmon/{slug}.toml`\n"
        result += "\n"

    result += "## API Data\n\n"
    result += f"https://experimenter.services.mozilla.com/nimbus/{slug}/summary\n"

    return [TextContent(type="text", text=result)]


# --- Repo config files (jetstream / opmon / looker) ---

async def handle_list_experiment_configs(arguments: dict[str, Any]) -> list[TextContent]:
    """List all configuration files of a given type."""
    config_type = arguments["config_type"]
    config_dir = get_repo_path() / config_type

    if not config_dir.exists():
        return [TextContent(type="text", text=f"Directory '{config_type}' not found")]

    configs = [
        {"slug": f.stem, "path": str(f.relative_to(get_repo_path()))}
        for f in config_dir.glob("*.toml")
        if f.is_file()
    ]

    result = f"# {config_type.title()} Configurations\n\n"
    result += f"**Total configs:** {len(configs)}\n\n"
    for config in sorted(configs, key=lambda x: x["slug"]):
        result += f"- `{config['slug']}`\n"

    return [TextContent(type="text", text=result)]


async def handle_get_experiment_config(arguments: dict[str, Any]) -> list[TextContent]:
    """Get the contents of a configuration file."""
    config_type = arguments["config_type"]
    config_slug = arguments.get("config_slug") or arguments.get("experiment_slug")

    config_file = get_repo_path() / config_type / f"{config_slug}.toml"

    if not config_file.exists():
        return [TextContent(type="text", text=f"Configuration file '{config_slug}.toml' not found in {config_type}/")]

    content = config_file.read_text()
    result = f"# Config: {config_slug}\n\n"
    result += f"**Path:** `{config_type}/{config_slug}.toml`\n\n"
    result += f"## Configuration\n\n```toml\n{content}```\n"

    return [TextContent(type="text", text=result)]


async def handle_create_experiment_config(arguments: dict[str, Any]) -> list[TextContent]:
    """Create a new configuration file."""
    new_config_slug = arguments.get("new_config_slug") or arguments.get("new_experiment_slug")
    config_type = arguments["config_type"]
    base_config_slug = arguments.get("base_config_slug")
    config_content = arguments.get("config_content")

    repo_path = get_repo_path()
    new_config_file = repo_path / config_type / f"{new_config_slug}.toml"

    if new_config_file.exists():
        return [TextContent(type="text", text=f"Error: Configuration file '{new_config_slug}.toml' already exists in {config_type}/")]

    if base_config_slug:
        base_config_file = repo_path / config_type / f"{base_config_slug}.toml"
        if not base_config_file.exists():
            return [TextContent(type="text", text=f"Error: Base configuration '{base_config_slug}.toml' not found in {config_type}/")]
        content = base_config_file.read_text()
    elif config_content:
        content = config_content
    else:
        return [TextContent(type="text", text="Error: Either 'base_config_slug' or 'config_content' must be provided")]

    new_config_file.write_text(content)

    result = f"# Created Config: {new_config_slug}\n\n"
    result += f"**Path:** `{config_type}/{new_config_slug}.toml`\n\n"
    if base_config_slug:
        result += f"**Copied from:** `{base_config_slug}.toml`\n\n"
    result += f"## Content\n\n```toml\n{content}```\n\n"
    result += "## Next Steps\n\n"
    result += "1. Review and customize the configuration for your experiment\n"
    result += "2. Update metric references to match your needs\n"
    result += "3. Commit and push the configuration to the repository\n"

    return [TextContent(type="text", text=result)]


async def handle_generate_config_template(arguments: dict[str, Any]) -> list[TextContent]:
    """Generate a template for a new configuration."""
    config_type = arguments["config_type"]
    template_type = arguments["template_type"]
    platform = arguments["platform"]

    if config_type == "jetstream":
        return await _generate_jetstream_template(template_type, platform)
    elif config_type == "opmon":
        return await _generate_opmon_template(template_type, platform)
    elif config_type == "looker":
        return await _generate_looker_template(platform)
    else:
        return [TextContent(type="text", text=f"Unknown config type: {config_type}")]


async def _generate_jetstream_template(template_type: str, platform: str) -> list[TextContent]:
    templates = {
        "basic": f"""[experiment]
# enrollment_period = 7
# reference_branch = "control"

[metrics]
daily = []
weekly = []
28_day = []
overall = []

# Reference metrics from the {platform} platform definitions
# Example: weekly = ["active_hours", "uri_count"]
""",
        "with_segments": f"""[experiment]
segments = ["my_segment"]

[segments.data_sources.my_data_source]
from_expression = \"\"\"(
  SELECT * FROM `moz-fx-data-shared-prod.telemetry.clients_daily`
)\"\"\"
window_start = 0
window_end = 28

[segments.my_segment]
select_expression = \"\"\"
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

[metrics.my_metric]
select_expression = \"\"\"
  {{{{agg_sum("column_name")}}}}
\"\"\"
data_source = "main"
friendly_name = "My Custom Metric"
description = "Description of what this metric measures"
bigger_is_better = true

[metrics.my_metric.statistics.binomial]
""",
        "with_custom_data_source": f"""[experiment]

[data_sources.my_custom_source]
from_expression = \"\"\"
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
""",
    }

    template = templates.get(template_type, "")
    result = f"# Jetstream Experiment Configuration Template: {template_type}\n\n"
    result += f"**Platform:** {platform}\n\n"
    result += f"## Template\n\n```toml\n{template}```\n\n"
    result += "## Key Configuration Sections\n\n"
    result += "### [experiment]\n"
    result += "- `segments`: List of user segments to analyze\n"
    result += "- `enrollment_period`: Duration of enrollment in days\n"
    result += "- `reference_branch`: Control branch name\n\n"
    result += "### [metrics]\n"
    result += "- `daily` / `weekly` / `28_day` / `overall`: Metrics per analysis window\n\n"
    result += "### Custom Metrics\n"
    result += "Define with `[metrics.metric_name]` including `select_expression`, `data_source`, `friendly_name`, `description`\n\n"
    result += "## Documentation\n\nhttps://experimenter.info/deep-dives/jetstream/configuration\n"

    return [TextContent(type="text", text=result)]


async def _generate_opmon_template(template_type: str, platform: str) -> list[TextContent]:
    templates = {
        "basic": f"""[project]
name = "My Monitoring Project"
platform = "{platform}"
xaxis = "submission_date"
start_date = "2025-01-01"
skip_default_metrics = false

metrics = ["active_hours", "uri_count"]

[project.population]
data_source = "main"
monitor_entire_population = true

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

dimensions = ["country", "channel"]
metrics = ["active_hours"]

[project.population]
data_source = "main"
monitor_entire_population = true

[metrics.active_hours]
data_source = "main"
select_expression = "{{{{agg_sum('active_hours_sum')}}}}"
type = "scalar"
friendly_name = "Active Hours"
description = "Total active hours"

[metrics.active_hours.statistics]
sum = {{}}

[data_sources.main]
from_expression = "`moz-fx-data-shared-prod.telemetry.clients_daily`"
""",
    }

    template = templates.get(template_type, templates["basic"])
    result = f"# OpMon Configuration Template: {template_type}\n\n"
    result += f"**Platform:** {platform}\n\n"
    result += f"## Template\n\n```toml\n{template}```\n\n"
    result += "## Key Configuration Sections\n\n"
    result += "### [project]\n"
    result += "- `name`, `platform`, `xaxis`, `start_date`\n"
    result += "- `dimensions`: Optional breakdown dimensions\n\n"
    result += "### [project.population]\n"
    result += "- `data_source`, `monitor_entire_population`, optional `criteria`\n\n"
    result += "## Documentation\n\nhttps://docs.telemetry.mozilla.org/cookbooks/operational_monitoring.html\n"

    return [TextContent(type="text", text=result)]


async def _generate_looker_template(platform: str) -> list[TextContent]:
    template = f"""# Looker configurations are stored in looker/definitions/

[data_sources.'*']
columns_as_dimensions = true

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

    result = "# Looker Configuration Template\n\n"
    result += f"**Platform:** {platform}\n\n"
    result += f"## Template\n\n```toml\n{template}```\n\n"
    result += "## Key Configuration Notes\n\n"
    result += "- Looker configs are stored in `looker/definitions/` directory\n"
    result += "- Use `columns_as_dimensions = true` to enable all columns as Looker dimensions\n"
    result += "- Define custom metrics and data sources as needed\n"

    return [TextContent(type="text", text=result)]
