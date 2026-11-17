import math
import re
from collections.abc import Mapping
from enum import Enum, StrEnum
from typing import Any, TypeGuard

import attr

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
NO_ACTIVITY_DAYS = 30
MAX_WITHIN_DAYS = 28
JINJA_OPEN = "{{"
JINJA_CLOSE = "}}"
COMBINED = "{combined}"


class Aggregation(StrEnum):
    SUM = "sum"
    SUM_WHERE = "sum_where"
    COUNT = "count"
    COUNT_WHERE = "count_where"
    ANY = "any"
    RECENCY_WITHIN = "recency_within"


class Combine(StrEnum):
    SUM = "SUM"
    MIN = "MIN"


class RecencyEncoding(StrEnum):
    BITS28 = "bits28"
    DAYS = "days"


class Operator(StrEnum):
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    EQ = "="
    NE = "!="
    LIKE = "LIKE"
    IN = "IN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"


THRESHOLD_OPERATORS = {
    Operator.GT,
    Operator.GE,
    Operator.LT,
    Operator.LE,
    Operator.EQ,
    Operator.NE,
}

COMPARISON_OPERATORS = THRESHOLD_OPERATORS | {Operator.LIKE}

LIST_OPERATORS = {Operator.IN}

COLUMN_AGGREGATIONS = {Aggregation.SUM, Aggregation.COUNT, Aggregation.RECENCY_WITHIN}
CONDITION_AGGREGATIONS = {Aggregation.COUNT_WHERE, Aggregation.ANY}
VALUE_AND_CONDITION_AGGREGATIONS = {Aggregation.SUM_WHERE}

KEEP_NULLS_AGGREGATIONS = {Aggregation.SUM, Aggregation.SUM_WHERE, Aggregation.ANY}
DEFAULT_KEEP_NULLS = False

CLAUSE_KEYS = {"column", "op", "value"}
THRESHOLD_KEYS = {"op", "value"}
COLUMN_FORM_KEYS = {"map", "key", "json", "path"}
ANY_OF_KEYS = {"any_of"}


def is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def is_positive_int(value: Any) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate_identifier(column: Any, context: str) -> None:
    if not isinstance(column, str) or not IDENTIFIER.match(column):
        raise ValueError(f"{context}: column '{column}' must be a plain column name or dotted path")


@attr.s(auto_attribs=True, frozen=True)
class ColumnForm:
    """A derived column reference, in place of a plain column name: either a keyed-map
    extraction (`map`, with an optional `key`) or a JSON field extraction (`json` and
    `path`)."""

    map: str | None = None
    key: str | None = None
    json: str | None = None
    path: str | None = None

    def __attrs_post_init__(self) -> None:
        if self.map is not None and self.json is not None:
            raise ValueError("column: declare either map or json, not both")
        if self.map is not None:
            validate_identifier(self.map, "column")
            if self.path is not None:
                raise ValueError("column: path is only valid with json")
            if self.key is not None and not isinstance(self.key, str):
                raise ValueError("column: key must be a string")
        elif self.json is not None:
            validate_identifier(self.json, "column")
            if self.key is not None:
                raise ValueError("column: key is not valid with json")
            if not isinstance(self.path, str):
                raise ValueError("column: json requires path")
        else:
            raise ValueError("column: must declare map or json")

    @property
    def sql(self) -> str:
        if self.map is not None:
            if self.key is not None:
                return f"mozfun.map.get_key({self.map}, {sql_value(self.key)})"
            return f"mozfun.map.extract_keyed_scalar_sum({self.map})"
        return f"JSON_VALUE({self.json}, {sql_value(f'$.{self.path}')})"

    @property
    def source_column(self) -> str:
        return self.map if self.map is not None else str(self.json)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ColumnForm":
        reject_unknown_keys(d, COLUMN_FORM_KEYS, "column")
        return cls(map=d.get("map"), key=d.get("key"), json=d.get("json"), path=d.get("path"))


ColumnReference = str | ColumnForm


def parse_column(value: Any) -> ColumnReference:
    if isinstance(value, Mapping):
        return ColumnForm.from_dict(value)
    return value


def validate_column(column: ColumnReference, context: str) -> None:
    if isinstance(column, ColumnForm):
        return
    validate_identifier(column, context)


def column_sql(column: ColumnReference | None) -> str:
    if isinstance(column, ColumnForm):
        return column.sql
    return str(column)


def column_source(column: ColumnReference | None) -> str:
    if isinstance(column, ColumnForm):
        return column.source_column
    return str(column)


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
    column: ColumnReference
    op: Operator | None = None
    value: Any = None

    def __attrs_post_init__(self) -> None:
        validate_column(self.column, "where clause")
        if self.op in LIST_OPERATORS:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError(
                    f"where clause on '{self.column}' with '{self.op}' requires a "
                    "non-empty list value"
                )
        elif self.op is None or self.op not in COMPARISON_OPERATORS:
            if self.value is not None:
                raise ValueError(f"where clause on '{self.column}' takes no value")
        elif self.value is None:
            raise ValueError(f"where clause on '{self.column}' with '{self.op}' requires a value")

    @property
    def sql(self) -> str:
        column_text = column_sql(self.column)
        if self.op is None:
            return column_text
        if self.op in LIST_OPERATORS:
            values = ", ".join(sql_value(v) for v in self.value)
            return f"{column_text} {self.op} ({values})"
        if self.op in COMPARISON_OPERATORS:
            return f"{column_text} {self.op} {sql_value(self.value)}"
        return f"{column_text} {self.op}"

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Clause":
        reject_unknown_keys(d, CLAUSE_KEYS, "where clause")
        if "column" not in d:
            raise ValueError("where clause requires a column")
        op = d.get("op")
        return cls(
            column=parse_column(d["column"]),
            op=None if op is None else to_enum(Operator, op, "where clause"),
            value=d.get("value"),
        )


@attr.s(auto_attribs=True, frozen=True)
class AnyOf:
    """A group of clauses joined with OR, in place of one AND'd clause in `where`."""

    clauses: list[Clause]

    def __attrs_post_init__(self) -> None:
        if len(self.clauses) < 2:
            raise ValueError("any_of requires at least two clauses")

    @property
    def sql(self) -> str:
        return " OR ".join(clause.sql for clause in self.clauses)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "AnyOf":
        reject_unknown_keys(d, ANY_OF_KEYS, "where clause")
        clauses = d.get("any_of")
        if not isinstance(clauses, list) or len(clauses) < 2:
            raise ValueError("any_of requires a list of at least two clauses")
        return cls(clauses=[Clause.from_dict(clause) for clause in clauses])


@attr.s(auto_attribs=True)
class Threshold:
    op: Operator
    value: int | float

    def __attrs_post_init__(self) -> None:
        if self.op not in THRESHOLD_OPERATORS:
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


def parse_condition(d: Mapping[str, Any]) -> Any:
    if "any_of" in d:
        return AnyOf.from_dict(d)
    return Clause.from_dict(d)


def predicate_sql(conditions: list[Any]) -> str:
    multiple = len(conditions) > 1
    parts = []
    for condition in conditions:
        text = condition.sql
        if multiple and isinstance(condition, AnyOf):
            text = f"({text})"
        parts.append(text)
    return " AND ".join(parts)


def recency_inner_expression(
    column: ColumnReference | None, encoding: RecencyEncoding | None
) -> str:
    column_text = column_sql(column)
    if encoding == RecencyEncoding.DAYS:
        return column_text
    return f"mozfun.bits28.days_since_seen({column_text})"


def aggregation_select_expression(
    aggregation: Aggregation,
    column: ColumnReference | None,
    conditions: list[Any],
    within_days: int | None,
    threshold: Threshold | None,
    scale: int | float | None,
    keep_nulls: bool = DEFAULT_KEEP_NULLS,
    encoding: RecencyEncoding | None = None,
) -> str:
    predicate = predicate_sql(conditions)
    column_text = column_sql(column)
    is_boolean = False
    if aggregation == Aggregation.SUM:
        expression = f"SUM({column_text})" if keep_nulls else macro_call("agg_sum", column_text)
    elif aggregation == Aggregation.SUM_WHERE:
        base = f"SUM(IF({predicate}, {column_text}, 0))"
        expression = base if keep_nulls else f"COALESCE({base}, 0)"
    elif aggregation == Aggregation.COUNT:
        expression = f"COUNT({column_text})"
    elif aggregation == Aggregation.COUNT_WHERE:
        expression = f"COUNTIF({predicate})"
    elif aggregation == Aggregation.ANY:
        expression = f"LOGICAL_OR({predicate})" if keep_nulls else macro_call("agg_any", predicate)
        is_boolean = True
    elif aggregation == Aggregation.RECENCY_WITHIN:
        inner = recency_inner_expression(column, encoding)
        expression = f"COALESCE(MIN({inner}), {NO_ACTIVITY_DAYS}) < {within_days}"
        is_boolean = True
    else:
        raise ValueError(f"unknown aggregation '{aggregation}'")

    if threshold is not None:
        if is_boolean:
            expression = f"CAST({expression} AS INT64)"
        expression = threshold.apply(expression)
        is_boolean = True
    if scale is not None:
        if is_boolean:
            expression = f"CAST({expression} AS INT64)"
        expression = f"{expression} * {sql_value(scale)}"

    return expression


@attr.s(auto_attribs=True, frozen=True)
class BucketedAggregation:
    """
    Per-bucket parts of a generated metric. bucket_aggregate reduces a unit's rows in one
    bucket, combine merges bucket values over a window, no_rows is the value for a unit with
    no rows, and finalize is applied once to the combined value, with {combined} standing
    for that value.
    """

    bucket_aggregate: str
    combine: Combine
    no_rows: str
    finalize: str

    def finalize_sql(self, combined: str) -> str:
        return self.finalize.replace(COMBINED, combined)


def aggregation_bucketed(
    aggregation: Aggregation,
    column: ColumnReference | None,
    conditions: list[Any],
    within_days: int | None,
    threshold: Threshold | None,
    scale: int | float | None,
    keep_nulls: bool = DEFAULT_KEEP_NULLS,
    encoding: RecencyEncoding | None = None,
) -> BucketedAggregation:
    predicate = predicate_sql(conditions)
    column_text = column_sql(column)
    combine = Combine.SUM
    no_rows = "0"
    finalize = COMBINED
    if aggregation == Aggregation.SUM:
        if keep_nulls:
            bucket_aggregate = f"SUM({column_text})"
            no_rows = "NULL"
        else:
            bucket_aggregate = f"COALESCE(SUM({column_text}), 0)"
    elif aggregation == Aggregation.SUM_WHERE:
        base = f"SUM(IF({predicate}, {column_text}, 0))"
        if keep_nulls:
            bucket_aggregate = base
            no_rows = "NULL"
        else:
            bucket_aggregate = f"COALESCE({base}, 0)"
    elif aggregation == Aggregation.COUNT:
        bucket_aggregate = f"COUNT({column_text})"
    elif aggregation == Aggregation.COUNT_WHERE:
        bucket_aggregate = f"COUNTIF({predicate})"
    elif aggregation == Aggregation.ANY:
        bucket_aggregate = f"COUNTIF({predicate})"
        finalize = f"CAST({COMBINED} > 0 AS INT64)"
        if keep_nulls:
            no_rows = "NULL"
    elif aggregation == Aggregation.RECENCY_WITHIN:
        inner = recency_inner_expression(column, encoding)
        bucket_aggregate = f"COALESCE(MIN({inner}), {NO_ACTIVITY_DAYS})"
        combine = Combine.MIN
        no_rows = str(NO_ACTIVITY_DAYS)
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
