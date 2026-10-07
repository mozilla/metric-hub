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

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Threshold":
        reject_unknown_keys(d, THRESHOLD_KEYS, "threshold")
        if "op" not in d or "value" not in d:
            raise ValueError("threshold requires op and value")
        return cls(op=to_enum(Operator, d["op"], "threshold"), value=d["value"])
