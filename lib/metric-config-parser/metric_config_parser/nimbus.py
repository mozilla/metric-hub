from collections.abc import Mapping
from enum import Enum, auto
from pathlib import Path
from typing import Any

import attr
import toml

from .aggregation import reject_unknown_keys
from .metric import MetricDefinition
from .util import converter

NIMBUS_DIR = "nimbus"
DEFINITIONS_DIR = "definitions"
DEFAULTS_DIR = "defaults"
OUTCOMES_DIR = "outcomes"


class NimbusConfigKind(Enum):
    DEFINITIONS = auto()
    DEFAULTS = auto()
    OUTCOMES = auto()


NIMBUS_METRIC_KEYS = {
    "data_source",
    "aggregation",
    "column",
    "where",
    "threshold",
    "scale",
    "coalesce",
    "within_days",
    "cumulative_window",
    "incremental_window",
    "repeat_windows",
    "statistics",
    "friendly_name",
    "description",
    "bigger_is_better",
    "category",
    "owner",
    "deprecated",
    "level",
}


@attr.s(auto_attribs=True, frozen=True)
class NimbusDefinitionMismatch:
    app_name: str
    metric: str
    nimbus_select_expression: str
    definitions_select_expression: str | None
    nimbus_data_source: str | None
    definitions_data_source: str | None
    outcome: str | None = None

    def __str__(self) -> str:
        if self.outcome is not None:
            match_target = f"outcomes/{self.app_name}/{self.outcome}.toml"
            label = f"outcomes/{self.app_name}/{self.outcome}"
        else:
            match_target = f"definitions/{self.app_name}.toml"
            label = "definitions"
        return (
            f"Metric '{self.metric}' in {NIMBUS_DIR}/definitions/{self.app_name}.toml does not "
            f"match {match_target}\n"
            f"  {NIMBUS_DIR}/definitions: data_source={self.nimbus_data_source}, "
            f"select_expression={self.nimbus_select_expression}\n"
            f"  {label}: data_source={self.definitions_data_source}, "
            f"select_expression={self.definitions_select_expression}"
        )


@attr.s(auto_attribs=True)
class NimbusSpec:
    """Metric definitions from a nimbus/definitions/<application>.toml, a
    nimbus/defaults/<application>.toml, or one outcome's
    nimbus/outcomes/<application>/<outcome>.toml."""

    metrics: dict[str, MetricDefinition] = attr.Factory(dict)

    @classmethod
    def from_dict(
        cls, d: Mapping[str, Any], platform: str, context: str | None = None
    ) -> "NimbusSpec":
        if context is None:
            context = f"{NIMBUS_DIR}/{DEFINITIONS_DIR}/{platform}.toml"
        reject_unknown_keys(d, {"metrics"}, context)
        metrics = {}
        for name, metric in d.get("metrics", {}).items():
            metric_context = f"{context}: metric '{name}'"
            if "select_expression" in metric:
                raise ValueError(
                    f"{metric_context}: select_expression is not allowed. Use aggregation instead."
                )
            reject_unknown_keys(metric, NIMBUS_METRIC_KEYS, metric_context)
            for required in ("data_source", "aggregation"):
                if required not in metric:
                    raise ValueError(f"{metric_context}: {required} is required")
            metrics[name] = converter.structure({"name": name, **metric}, MetricDefinition)
        return cls(metrics=metrics)

    @classmethod
    def from_file(cls, path: Path) -> "NimbusSpec":
        if path.parent.parent.name == OUTCOMES_DIR:
            platform = path.parent.name
            context = f"{NIMBUS_DIR}/{OUTCOMES_DIR}/{platform}/{path.stem}.toml"
        elif path.parent.name == DEFAULTS_DIR:
            platform = path.stem
            context = f"{NIMBUS_DIR}/{DEFAULTS_DIR}/{path.stem}.toml"
        else:
            platform = path.stem
            context = f"{NIMBUS_DIR}/{DEFINITIONS_DIR}/{path.stem}.toml"
        return cls.from_dict(toml.load(str(path)), platform=platform, context=context)
