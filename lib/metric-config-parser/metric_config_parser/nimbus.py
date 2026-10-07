from collections.abc import Mapping
from pathlib import Path
from typing import Any

import attr
import toml

from .aggregation import reject_unknown_keys
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


@attr.s(auto_attribs=True)
class NimbusSpec:
    """Metric definitions from a nimbus/definitions/<application>.toml file."""

    metrics: dict[str, MetricDefinition] = attr.Factory(dict)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], platform: str) -> "NimbusSpec":
        context = f"{NIMBUS_DIR}/definitions/{platform}.toml"
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
        return cls.from_dict(toml.load(str(path)), platform=path.stem)
