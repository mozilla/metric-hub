from collections.abc import Mapping
from pathlib import Path
from typing import Any

import attr
import toml

from .aggregation import reject_unknown_keys
from .data_source import DataSourceDefinition
from .metric import MetricDefinition
from .util import converter

NIMBUS_DIR = "nimbus"

NIMBUS_METRIC_KEYS = {
    "data_source",
    "aggregation",
    "column",
    "where",
    "threshold",
    "scale",
    "coalesce",
    "cast_as_int",
    "encoding",
    "within_days",
    "cumulative_window",
    "incremental_window",
    "repeat_windows",
    "winsorize_quantile",
    "winsorize_threshold",
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

    def __str__(self) -> str:
        return (
            f"Metric '{self.metric}' in {NIMBUS_DIR}/definitions/{self.app_name}.toml does not "
            f"match definitions/{self.app_name}.toml\n"
            f"  {NIMBUS_DIR}/definitions: data_source={self.nimbus_data_source}, "
            f"select_expression={self.nimbus_select_expression}\n"
            f"  definitions: data_source={self.definitions_data_source}, "
            f"select_expression={self.definitions_select_expression}"
        )


@attr.s(auto_attribs=True)
class NimbusSpec:
    """Metric definitions from a nimbus/definitions/<application>.toml file."""

    metrics: dict[str, MetricDefinition] = attr.Factory(dict)
    data_sources: dict[str, DataSourceDefinition] = attr.Factory(dict)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], platform: str) -> "NimbusSpec":
        context = f"{NIMBUS_DIR}/definitions/{platform}.toml"
        reject_unknown_keys(d, {"metrics", "data_sources"}, context)
        data_sources = {
            name: converter.structure(
                {"name": name, **{key.lower(): value for key, value in data_source.items()}},
                DataSourceDefinition,
            )
            for name, data_source in d.get("data_sources", {}).items()
        }
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
        return cls(metrics=metrics, data_sources=data_sources)

    @classmethod
    def from_file(cls, path: Path) -> "NimbusSpec":
        return cls.from_dict(toml.load(str(path)), platform=path.stem)
