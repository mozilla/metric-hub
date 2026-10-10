import math
import re
from collections.abc import Mapping
from enum import Enum, StrEnum
from typing import Any

import attr

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Aggregation(StrEnum):
    SUM = "sum"
    COUNT = "count"
    COUNT_WHERE = "count_where"
    ANY = "any"
    RECENCY_WITHIN = "recency_within"


class Combine(StrEnum):
    SUM = "SUM"
    MIN = "MIN"


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

CLAUSE_KEYS = {"column", "op", "value"}
THRESHOLD_KEYS = {"op", "value"}

NO_ACTIVITY_DAYS = 30
JINJA_OPEN = "{{"
JINJA_CLOSE = "}}"
COMBINED = "{combined}"


def is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate_identifier(column: Any, context: str) -> None:
    if not isinstance(column, str) or not IDENTIFIER.match(column):
        raise ValueError(f"{context}: column '{column}' must be a plain column name")


def to_enum(enum_cls: type[Enum], value: Any, context: str) -> Any:
    try:
        return enum_cls(value)
    except ValueError:
        raise ValueError(
            f"{context}: '{value}' is not one of {[member.value for member in enum_cls]}"
        ) from None


def sql_value(value: Any) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if is_number(value):
        if not math.isfinite(value):
            raise ValueError(f"value '{value}' must be a finite number")
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("'", "\\'").replace("{", "\\x7b")
        return f"'{escaped}'"
    raise ValueError(f"value '{value}' must be a number, string or boolean")


def macro_call(name: str, argument: str) -> str:
    escaped = argument.replace("\\", "\\\\").replace('"', '\\"')
    return f'{JINJA_OPEN}{name}("{escaped}"){JINJA_CLOSE}'


def reject_unknown_keys(d: Mapping[str, Any], allowed: set[str], context: str) -> None:
    unknown = set(d) - allowed
    if unknown:
        raise ValueError(f"{context}: unexpected keys {sorted(unknown)}")


@attr.s(auto_attribs=True)
class Clause:
    column: str
    op: Operator | None = None
    value: Any = None

    def __attrs_post_init__(self) -> None:
        validate_identifier(self.column, "where clause")
        if self.op is None or self.op not in COMPARISON_OPERATORS:
            if self.value is not None:
                raise ValueError(f"where clause on '{self.column}' takes no value")
        elif self.value is None:
            raise ValueError(f"where clause on '{self.column}' with '{self.op}' requires a value")

    @property
    def sql(self) -> str:
        if self.op is None:
            return self.column
        if self.op in COMPARISON_OPERATORS:
            return f"{self.column} {self.op} {sql_value(self.value)}"
        return f"{self.column} {self.op}"

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Clause":
        reject_unknown_keys(d, CLAUSE_KEYS, "where clause")
        if "column" not in d:
            raise ValueError("where clause requires a column")
        op = d.get("op")
        return cls(
            column=d["column"],
            op=None if op is None else to_enum(Operator, op, "where clause"),
            value=d.get("value"),
        )


@attr.s(auto_attribs=True)
class Threshold:
    op: Operator
    value: int | float

    def __attrs_post_init__(self) -> None:
        if self.op not in COMPARISON_OPERATORS:
            raise ValueError(f"threshold operator '{self.op}' must be a comparison")
        if not is_number(self.value):
            raise ValueError(f"threshold value '{self.value}' must be a number")

    def apply(self, expression: str) -> str:
        return f"{expression} {self.op} {sql_value(self.value)}"

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Threshold":
        reject_unknown_keys(d, THRESHOLD_KEYS, "threshold")
        if "op" not in d or "value" not in d:
            raise ValueError("threshold requires op and value")
        return cls(op=to_enum(Operator, d["op"], "threshold"), value=d["value"])


def predicate_sql(conditions: list[Clause]) -> str:
    return " AND ".join(clause.sql for clause in conditions)


def aggregation_select_expression(
    aggregation: Aggregation,
    column: str | None,
    conditions: list[Clause],
    within_days: int | None,
    threshold: Threshold | None,
    scale: int | float | None,
) -> str:
    predicate = predicate_sql(conditions)
    if aggregation == Aggregation.SUM:
        expression, is_boolean = f'{JINJA_OPEN}agg_sum("{column}"){JINJA_CLOSE}', False
    elif aggregation == Aggregation.COUNT:
        expression, is_boolean = f"COUNT({column})", False
    elif aggregation == Aggregation.COUNT_WHERE:
        expression, is_boolean = f"COUNTIF({predicate})", False
    elif aggregation == Aggregation.ANY:
        expression, is_boolean = macro_call("agg_any", predicate), True
    elif aggregation == Aggregation.RECENCY_WITHIN:
        expression = (
            f"COALESCE(MIN(mozfun.bits28.days_since_seen({column})), {NO_ACTIVITY_DAYS})"
            f" < {within_days}"
        )
        is_boolean = True
    else:
        raise ValueError(f"unknown aggregation '{aggregation}'")

    if threshold is not None:
        if is_boolean:
            expression = f"CAST({expression} AS INT64)"
        expression, is_boolean = threshold.apply(expression), True
    if scale is not None:
        if is_boolean:
            expression = f"CAST({expression} AS INT64)"
        expression = f"{expression} * {sql_value(scale)}"
    return expression


@attr.s(auto_attribs=True, frozen=True)
class BucketedAggregation:
    bucket_aggregate: str
    combine: Combine
    no_rows: str
    finalize: str

    def finalize_sql(self, combined: str) -> str:
        return self.finalize.replace(COMBINED, combined)


def aggregation_bucketed(
    aggregation: Aggregation,
    column: str | None,
    conditions: list[Clause],
    within_days: int | None,
    threshold: Threshold | None,
    scale: int | float | None,
) -> BucketedAggregation:
    predicate = predicate_sql(conditions)
    combine, no_rows, finalize = Combine.SUM, "0", COMBINED
    if aggregation == Aggregation.SUM:
        bucket_aggregate = f"SUM({column})"
    elif aggregation == Aggregation.COUNT:
        bucket_aggregate = f"COUNT({column})"
    elif aggregation == Aggregation.COUNT_WHERE:
        bucket_aggregate = f"COUNTIF({predicate})"
    elif aggregation == Aggregation.ANY:
        bucket_aggregate = f"COUNTIF({predicate})"
        finalize = f"CAST({COMBINED} > 0 AS INT64)"
    elif aggregation == Aggregation.RECENCY_WITHIN:
        bucket_aggregate = f"MIN(mozfun.bits28.days_since_seen({column}))"
        combine, no_rows = Combine.MIN, str(NO_ACTIVITY_DAYS)
        finalize = f"CAST({COMBINED} < {within_days} AS INT64)"
    else:
        raise ValueError(f"unknown aggregation '{aggregation}'")

    if threshold is not None:
        finalize = f"CAST({threshold.apply(finalize)} AS INT64)"
    if scale is not None:
        finalize = f"({finalize}) * {sql_value(scale)}"
    return BucketedAggregation(
        bucket_aggregate=bucket_aggregate, combine=combine, no_rows=no_rows, finalize=finalize
    )
