import re
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

import attr
import toml

METRIC_V2_DIR = "definitions_v2"

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Aggregation(StrEnum):
    SUM = "sum"
    COUNT = "count"
    COUNT_WHERE = "count_where"
    ANY = "any"
    RECENCY_WITHIN = "recency_within"


class Operator(StrEnum):
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    EQ = "="
    NE = "!="
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"


COMPARISON_OPERATORS = {
    Operator.GT,
    Operator.GE,
    Operator.LT,
    Operator.LE,
    Operator.EQ,
    Operator.NE,
}

COLUMN_AGGREGATIONS = {Aggregation.SUM, Aggregation.COUNT, Aggregation.RECENCY_WITHIN}
CONDITION_AGGREGATIONS = {Aggregation.COUNT_WHERE, Aggregation.ANY}

METRIC_KEYS = {
    "data_source",
    "aggregation",
    "column",
    "where",
    "threshold",
    "scale",
    "within_days",
    "cumulative_window",
    "incremental_window",
    "repeat_windows",
    "statistics",
    "friendly_name",
    "description",
    "bigger_is_better",
}
CLAUSE_KEYS = {"column", "op", "value"}
THRESHOLD_KEYS = {"op", "value"}


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_identifier(column: str, context: str) -> None:
    if not isinstance(column, str) or not IDENTIFIER.match(column):
        raise ValueError(f"{context}: column '{column}' must be a plain column name")


def _to_enum(enum_cls: type[StrEnum], value: Any, context: str) -> Any:
    try:
        return enum_cls(value)
    except ValueError:
        raise ValueError(
            f"{context}: '{value}' is not one of {[member.value for member in enum_cls]}"
        ) from None


def _reject_unknown_keys(d: Mapping[str, Any], allowed: set[str], context: str) -> None:
    unknown = set(d) - allowed
    if unknown:
        raise ValueError(f"{context}: unexpected keys {sorted(unknown)}")


@attr.s(auto_attribs=True)
class Clause:
    column: str
    op: Operator | None = None
    value: Any = None

    def __attrs_post_init__(self) -> None:
        _validate_identifier(self.column, "where clause")
        if self.op is None or self.op not in COMPARISON_OPERATORS:
            if self.value is not None:
                raise ValueError(f"where clause on '{self.column}' takes no value")
        elif self.value is None:
            raise ValueError(f"where clause on '{self.column}' with '{self.op}' requires a value")

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], context: str) -> "Clause":
        _reject_unknown_keys(d, CLAUSE_KEYS, context)
        if "column" not in d:
            raise ValueError(f"{context}: where clause requires a column")
        op = d.get("op")
        return cls(
            column=d["column"],
            op=None if op is None else _to_enum(Operator, op, context),
            value=d.get("value"),
        )


@attr.s(auto_attribs=True)
class Threshold:
    op: Operator
    value: int | float

    def __attrs_post_init__(self) -> None:
        if self.op not in COMPARISON_OPERATORS:
            raise ValueError(f"threshold operator '{self.op}' must be a comparison")
        if not _is_number(self.value):
            raise ValueError(f"threshold value '{self.value}' must be a number")

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], context: str) -> "Threshold":
        _reject_unknown_keys(d, THRESHOLD_KEYS, context)
        if "op" not in d or "value" not in d:
            raise ValueError(f"{context}: threshold requires op and value")
        return cls(op=_to_enum(Operator, d["op"], context), value=d["value"])


@attr.s(auto_attribs=True)
class MetricV2Definition:
    name: str
    data_source: str
    aggregation: Aggregation
    column: str | None = None
    where: list[Clause] = attr.Factory(list)
    threshold: Threshold | None = None
    scale: int | float | None = None
    within_days: int | None = None
    cumulative_window: int | None = None
    incremental_window: int | None = None
    repeat_windows: bool = False
    statistics: dict[str, dict] | None = None
    friendly_name: str | None = None
    description: str | None = None
    bigger_is_better: bool = True

    def __attrs_post_init__(self) -> None:
        context = f"metric '{self.name}'"
        if self.aggregation not in COLUMN_AGGREGATIONS | CONDITION_AGGREGATIONS:
            raise ValueError(f"{context}: unknown aggregation '{self.aggregation}'")
        if self.column is not None:
            _validate_identifier(self.column, context)

        if self.aggregation in COLUMN_AGGREGATIONS:
            if self.column is None:
                raise ValueError(f"{context}: '{self.aggregation}' requires a column")
            if self.where:
                raise ValueError(f"{context}: '{self.aggregation}' does not take where")
        elif (self.column is None) == (not self.where):
            raise ValueError(
                f"{context}: '{self.aggregation}' requires exactly one of column or where"
            )

        if self.aggregation == Aggregation.RECENCY_WITHIN:
            if not _is_positive_int(self.within_days):
                raise ValueError(f"{context}: within_days must be a positive integer")
        elif self.within_days is not None:
            raise ValueError(f"{context}: within_days is only valid for recency_within")

        if self.scale is not None and not _is_number(self.scale):
            raise ValueError(f"{context}: scale must be a number")

        if self.cumulative_window is not None and not _is_positive_int(self.cumulative_window):
            raise ValueError(f"{context}: cumulative_window must be a positive integer")
        if self.incremental_window is not None and not _is_positive_int(self.incremental_window):
            raise ValueError(f"{context}: incremental_window must be a positive integer")
        if not isinstance(self.repeat_windows, bool):
            raise ValueError(f"{context}: repeat_windows must be a boolean")
        if (
            self.repeat_windows
            and self.cumulative_window is None
            and self.incremental_window is None
        ):
            raise ValueError(
                f"{context}: repeat_windows requires cumulative_window or incremental_window"
            )

        if self.statistics is not None and not (
            isinstance(self.statistics, dict)
            and all(isinstance(params, dict) for params in self.statistics.values())
        ):
            raise ValueError(f"{context}: statistics must be a table of tables")

    @property
    def conditions(self) -> list[Clause]:
        if self.aggregation in CONDITION_AGGREGATIONS and self.column is not None:
            return [Clause(column=self.column)]
        return self.where

    @classmethod
    def from_dict(cls, name: str, d: Mapping[str, Any]) -> "MetricV2Definition":
        context = f"metric '{name}'"
        _reject_unknown_keys(d, METRIC_KEYS, context)
        for required in ("data_source", "aggregation"):
            if required not in d:
                raise ValueError(f"{context}: {required} is required")
        threshold = d.get("threshold")
        return cls(
            name=name,
            data_source=d["data_source"],
            aggregation=_to_enum(Aggregation, d["aggregation"], context),
            column=d.get("column"),
            where=[Clause.from_dict(clause, context) for clause in d.get("where", [])],
            threshold=None if threshold is None else Threshold.from_dict(threshold, context),
            scale=d.get("scale"),
            within_days=d.get("within_days"),
            cumulative_window=d.get("cumulative_window"),
            incremental_window=d.get("incremental_window"),
            repeat_windows=d.get("repeat_windows", False),
            statistics=d.get("statistics"),
            friendly_name=d.get("friendly_name"),
            description=d.get("description"),
            bigger_is_better=d.get("bigger_is_better", True),
        )


@attr.s(auto_attribs=True)
class MetricV2Spec:
    dataset: str
    metrics: dict[str, MetricV2Definition] = attr.Factory(dict)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], dataset: str) -> "MetricV2Spec":
        _reject_unknown_keys(d, {"metrics"}, f"{METRIC_V2_DIR}/{dataset}")
        metrics = {
            name: MetricV2Definition.from_dict(name, cfg)
            for name, cfg in d.get("metrics", {}).items()
        }
        return cls(dataset=dataset, metrics=metrics)

    @classmethod
    def from_file(cls, path: Path) -> "MetricV2Spec":
        return cls.from_dict(toml.load(str(path)), dataset=path.stem)
