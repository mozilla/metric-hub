from collections.abc import Mapping
from typing import Any

import attr

from .data_source import DataSourcesSpec
from .metric import MetricDefinition, MetricReference
from .parameter import ParameterSpec
from .util import converter


@attr.s(auto_attribs=True)
class OutcomeSpec:
    """Represents an outcome snippet."""

    friendly_name: str
    description: str
    metrics: dict[str, MetricDefinition] = attr.Factory(dict)
    default_metrics: list[MetricReference] | None = attr.ib(None)
    data_sources: DataSourcesSpec = attr.Factory(DataSourcesSpec)
    parameters: ParameterSpec = attr.Factory(ParameterSpec)
    # Optional per-period metric-name lists, mirroring MetricsSpec. When any are
    # set, they control which analysis windows the outcome's metrics compute in;
    # when all are empty, merge_outcome falls back to weekly + overall (the
    # historical behavior). The "days28" list is keyed as "28_day" in TOML.
    daily: list[MetricReference] = attr.Factory(list)
    weekly: list[MetricReference] = attr.Factory(list)
    days28: list[MetricReference] = attr.Factory(list)
    overall: list[MetricReference] = attr.Factory(list)
    preenrollment_weekly: list[MetricReference] = attr.Factory(list)
    preenrollment_days28: list[MetricReference] = attr.Factory(list)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "OutcomeSpec":
        params: dict[str, Any] = {}
        params["friendly_name"] = d["friendly_name"]
        params["description"] = d["description"]
        params["data_sources"] = converter.structure(d.get("data_sources", {}), DataSourcesSpec)
        params["metrics"] = {
            k: converter.structure(
                {"name": k, **{kk.lower(): vv for kk, vv in v.items()}},
                MetricDefinition,
            )
            for k, v in d.get("metrics", {}).items()
        }
        params["default_metrics"] = [
            converter.structure(m, MetricReference) for m in d.get("default_metrics", [])
        ]

        params["parameters"] = ParameterSpec.from_dict(d.get("parameters", {}))

        # Parse optional per-period metric lists. "days28" uses the "28_day"
        # TOML alias, matching MetricsSpec.from_dict.
        for period in (
            "daily",
            "weekly",
            "days28",
            "overall",
            "preenrollment_weekly",
            "preenrollment_days28",
        ):
            key = "28_day" if period == "days28" else period
            v = d.get(key, [])
            if not isinstance(v, list):
                raise ValueError(f"{key} should be a list of metrics")
            params[period] = [converter.structure(m, MetricReference) for m in v]

        # check that default metrics are actually defined in outcome
        for default_metric in params["default_metrics"]:
            if default_metric.name not in params["metrics"]:
                raise ValueError(f"Default metric {default_metric} is not defined in outcome.")

        return cls(**params)
