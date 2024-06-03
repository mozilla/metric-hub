import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from .metric import MetricDefinition

if TYPE_CHECKING:
    from .config import ConfigCollection

FILE_PATH = Path(os.path.dirname(__file__))
METRICS_QUERY = FILE_PATH / "templates" / "metrics_query.sql"
DATA_SOURCE_QUERY = FILE_PATH / "templates" / "data_source_query.sql"
DATA_SOURCE_MACROS = FILE_PATH / "templates" / "data_source_macros.j2"


def generate_metrics_sql(
    config_collection: "ConfigCollection",
    metrics: List[str],
    platform: str,
    group_by: Union[List[str], Dict[str, str]] = [],
    where: Optional[str] = None,
    group_by_client_id: bool = True,
    group_by_submission_date: bool = True,
) -> str:
    """Generates a SQL query for metrics and specified parameters."""
    metric_definitions: List[MetricDefinition] = []
    for slug in metrics:
        definition = config_collection.get_metric_definition(slug, platform)

        if definition is None:
            raise ValueError(f"No definition for metric {slug} on platform {platform} found.")

        metric_definitions.append(definition)

    metrics_per_data_source: Dict[str, Any] = {}
    for metric in metric_definitions:
        if metric.select_expression is None:
            raise ValueError(f"No definition for metric {metric.name}")

        metric.select_expression = (
            config_collection.get_env().from_string(metric.select_expression).render()
        )

        if metric.data_source is None:
            raise ValueError(f"No data source for metric {metric.name}")

        if metric.data_source.name in metrics_per_data_source:
            metrics_per_data_source[metric.data_source.name]["metrics"].append(metric)
        else:
            data_source = config_collection.get_data_source_definition(
                metric.data_source.name, platform
            )

            if data_source is None:
                raise ValueError(f"No valid data source definition found for metric {metric.name}")

            # default parameters need to be set explicitly otherwise they'll be None
            data_source.client_id_column = data_source.client_id_column or "client_id"
            data_source.submission_date_column = (
                data_source.submission_date_column or "submission_date"
            )

            metrics_per_data_source[metric.data_source.name] = {
                "data_source": data_source,
                "metrics": [metric],
            }

    # group by should be a dictionary with the key being the alias and
    # the value the potentially nested field;
    # it can also be specified as list if all fields are top-level fields that don't need an alias
    if isinstance(group_by, list):
        group_by = {g: g for g in group_by}

    macros_template = DATA_SOURCE_MACROS.read_text()
    template = METRICS_QUERY.read_text()

    # using `from_string()` in Jinja doens't support include statements, so
    # substituting them here manually
    template = template.replace("{% include 'data_source_macros.j2' %}", macros_template)
    return (
        config_collection.get_env()
        .from_string(template)
        .render(
            **{
                "metrics_per_data_source": metrics_per_data_source,
                "where": where,
                "group_by": group_by,
                "group_by_client_id": group_by_client_id,
                "group_by_submission_date": group_by_submission_date,
                "data_sources": {
                    slug: data_source
                    for definition in config_collection.definitions
                    for slug, data_source in definition.spec.data_sources.definitions.items()
                    if platform == definition.platform
                },
                "select_fields": True,
                "ignore_joins": False,
            }
        )
    )


def generate_data_source_sql(
    config_collection: "ConfigCollection",
    data_source: str,
    platform: str,
    where: Optional[str] = None,
    select_fields: bool = True,
    ignore_joins: bool = False,
) -> str:
    """Generates a SQL query for the specified data source."""
    template = DATA_SOURCE_QUERY.read_text()
    macros_template = DATA_SOURCE_MACROS.read_text()

    # using `from_string()` in Jinja doens't support include statements, so
    # substituting them here manually
    template = template.replace("{% include 'data_source_macros.j2' %}", macros_template)
    data_source_definition = config_collection.get_data_source_definition(data_source, platform)

    if data_source_definition is None:
        raise ValueError(f"No valid data source definition found for {data_source}")

    # default parameters need to be set explicitly otherwise they'll be None
    data_source_definition.client_id_column = data_source_definition.client_id_column or "client_id"
    data_source_definition.submission_date_column = (
        data_source_definition.submission_date_column or "submission_date"
    )
    return (
        config_collection.get_env()
        .from_string(template)
        .render(
            **{
                "data_source": data_source_definition,
                "data_sources": {
                    slug: data_source
                    for definition in config_collection.definitions
                    for slug, data_source in definition.spec.data_sources.definitions.items()
                    if platform == definition.platform
                },
                "where": where,
                "select_fields": select_fields,
                "ignore_joins": ignore_joins,
            }
        )
    )
