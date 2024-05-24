from typing import Any, Dict, List, Mapping, Optional

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
    metrics: Dict[str, MetricDefinition] = attr.Factory(dict)
    default_metrics: Optional[List[MetricReference]] = attr.ib(None)
    data_sources: DataSourcesSpec = attr.Factory(DataSourcesSpec)
    parameters: ParameterSpec = attr.Factory(ParameterSpec)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "OutcomeSpec":
        params: Dict[str, Any] = {}
        params["friendly_name"] = d["friendly_name"]
        params["description"] = d["description"]
        params["data_sources"] = converter.structure(d.get("data_sources", {}), DataSourcesSpec)
        params["metrics"] = {
            k: converter.structure(
                {"name": k, **dict((kk.lower(), vv) for kk, vv in v.items())}, MetricDefinition
            )
            for k, v in d.get("metrics", {}).items()
        }
        params["default_metrics"] = [
            converter.structure(m, MetricReference) for m in d.get("default_metrics", [])
        ]

        params["parameters"] = ParameterSpec.from_dict(d.get("parameters", dict()))

        # check that default metrics are actually defined in outcome
        for default_metric in params["default_metrics"]:
            if default_metric.name not in params["metrics"].keys():
                raise ValueError(f"Default metric {default_metric} is not defined in outcome.")

        return cls(**params)
