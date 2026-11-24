import attr

from .aggregation import DEFAULT_KEEP_NULLS, BucketedAggregation, aggregation_bucketed
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
    group_id_column: str
    analysis_units: tuple[str, ...]
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


def _projected_column(column: str) -> str:
    return column.replace(".", "__")


def _column_select_item(column: str) -> str:
    projected = _projected_column(column)
    if projected == column:
        return column
    return f"{column} AS {projected}"


def _validate_no_column_collisions(data_source_name: str, columns: set[str]) -> None:
    projected_to_column: dict[str, str] = {}
    for column in sorted(columns):
        projected = _projected_column(column)
        if projected in projected_to_column:
            raise ValueError(
                f"data source '{data_source_name}': columns '{projected_to_column[projected]}' "
                f"and '{column}' both project to '{projected}'"
            )
        projected_to_column[projected] = column


def _resolve_metric(name: str, metric: MetricDefinition) -> _ResolvedMetric:
    if metric.data_source is None or metric.aggregation is None:
        raise ValueError(f"nimbus metric '{name}' is missing data_source or aggregation")
    projected_column = None if metric.column is None else _projected_column(metric.column)
    projected_conditions = [
        attr.evolve(clause, column=_projected_column(clause.column)) for clause in metric.conditions
    ]
    bucketed = aggregation_bucketed(
        metric.aggregation,
        projected_column,
        projected_conditions,
        metric.within_days,
        metric.threshold,
        metric.scale,
        metric.keep_nulls if metric.keep_nulls is not None else DEFAULT_KEEP_NULLS,
        metric.encoding,
    )
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
        group_id_column=data_source.group_id_column,
        analysis_units=tuple(unit.value for unit in data_source.analysis_units),
        submission_date_column=data_source.submission_date_column,
        columns=tuple(_column_select_item(column) for column in sorted(columns)),
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

    for data_source_name, columns in columns_by_source.items():
        _validate_no_column_collisions(data_source_name, columns)

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
