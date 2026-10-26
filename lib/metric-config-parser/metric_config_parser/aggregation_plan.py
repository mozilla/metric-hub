import attr

from .aggregation import BucketedAggregation
from .config import ConfigCollection
from .definition import DefinitionSpec
from .errors import DefinitionNotFound
from .metric import MetricDefinition
from .project import ProjectConfiguration


@attr.s(auto_attribs=True, frozen=True)
class AggregationSource:
    data_source: str
    from_expression: str
    client_id_column: str
    submission_date_column: str
    columns: tuple[str, ...]


@attr.s(auto_attribs=True, frozen=True)
class AggregationMetric:
    name: str
    data_source: str
    aggregation: BucketedAggregation
    cumulative_window: int | None
    incremental_window: int | None
    repeat_windows: bool


@attr.s(auto_attribs=True, frozen=True)
class AggregationPlan:
    sources: dict[str, AggregationSource]
    metrics: dict[str, AggregationMetric]
    missing: list[str]


@attr.s(auto_attribs=True, frozen=True)
class _ResolvedMetric:
    name: str
    data_source_name: str
    aggregation: BucketedAggregation
    columns: set[str]
    cumulative_window: int | None
    incremental_window: int | None
    repeat_windows: bool


def _metric_columns(metric: MetricDefinition) -> set[str]:
    columns: set[str] = set()
    if metric.column is not None:
        columns.add(metric.column)
    for clause in metric.conditions:
        columns.add(clause.column)
    return columns


def _resolve_metric(name: str, metric: MetricDefinition) -> _ResolvedMetric:
    if metric.data_source is None or metric.aggregation is None:
        raise ValueError(f"nimbus metric '{name}' is missing data_source or aggregation")
    bucketed = metric.bucketed_aggregation
    if bucketed is None:
        raise ValueError(f"nimbus metric '{name}' has no bucketed aggregation")
    return _ResolvedMetric(
        name=name,
        data_source_name=metric.data_source.name,
        aggregation=bucketed,
        columns=_metric_columns(metric),
        cumulative_window=metric.cumulative_window,
        incremental_window=metric.incremental_window,
        repeat_windows=metric.repeat_windows,
    )


def _resolve_data_source(
    data_source_name: str, app_name: str, configs: ConfigCollection, columns: set[str]
) -> AggregationSource:
    data_source_definition = configs.get_data_source_definition(data_source_name, app_name)
    if data_source_definition is None:
        raise DefinitionNotFound(
            f"No data source '{data_source_name}' defined for app '{app_name}'"
        )
    data_source = data_source_definition.resolve(
        DefinitionSpec(), ProjectConfiguration(app_name=app_name), configs
    )
    return AggregationSource(
        data_source=data_source_name,
        from_expression=data_source.from_expr_for(None),
        client_id_column=data_source.client_id_column,
        submission_date_column=data_source.submission_date_column,
        columns=tuple(sorted(columns)),
    )


def aggregation_plan(
    configs: ConfigCollection, app_name: str, metric_names: list[str]
) -> AggregationPlan:
    missing: list[str] = []
    resolved: list[_ResolvedMetric] = []
    for name in sorted(metric_names):
        metric = configs.get_nimbus_metric_definition(name, app_name)
        if metric is None:
            missing.append(name)
        else:
            resolved.append(_resolve_metric(name, metric))

    columns_by_source: dict[str, set[str]] = {}
    for resolved_metric in resolved:
        columns_by_source.setdefault(resolved_metric.data_source_name, set()).update(
            resolved_metric.columns
        )

    sources = {
        data_source_name: _resolve_data_source(
            data_source_name, app_name, configs, columns_by_source[data_source_name]
        )
        for data_source_name in sorted(columns_by_source)
    }

    metrics = {
        resolved_metric.name: AggregationMetric(
            name=resolved_metric.name,
            data_source=resolved_metric.data_source_name,
            aggregation=resolved_metric.aggregation,
            cumulative_window=resolved_metric.cumulative_window,
            incremental_window=resolved_metric.incremental_window,
            repeat_windows=resolved_metric.repeat_windows,
        )
        for resolved_metric in sorted(resolved, key=lambda m: m.name)
    }

    return AggregationPlan(sources=sources, metrics=metrics, missing=missing)
