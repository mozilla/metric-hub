from typing import TYPE_CHECKING, Dict, List, Optional

import attr

from metric_config_parser.metric import MetricReference
from metric_config_parser.util import converter

if TYPE_CHECKING:
    from metric_config_parser.config import ConfigCollection
    from metric_config_parser.monitoring import MonitoringSpec
    from metric_config_parser.project import ProjectConfiguration


@attr.s(auto_attribs=True, kw_only=True)
class MetricGroup:
    """Represents a set of metrics that are related and should be displayed together."""

    name: str
    description: Optional[str] = None
    friendly_name: Optional[str] = None
    metrics: List[MetricReference] = attr.Factory(list)


@attr.s(auto_attribs=True)
class MetricGroupDefinition:
    """Describes the interface for defining a metric group in configuration."""

    name: str  # implicit in configuration
    friendly_name: Optional[str] = None
    description: Optional[str] = None
    metrics: List[MetricReference] = attr.Factory(list)

    def resolve(
        self, spec: "MonitoringSpec", _conf: "ProjectConfiguration", _configs: "ConfigCollection"
    ) -> MetricGroup:
        """Create and return a `MetricGroup` from the definition."""
        for metric_ref in self.metrics:
            if metric_ref not in spec.project.metrics:
                raise ValueError(
                    f"Metric {metric_ref} is part of metric group {self.name} "
                    + "but not referenced as project metric"
                )

        return MetricGroup(
            name=self.name,
            metrics=self.metrics,
            friendly_name=self.friendly_name,
            description=self.description,
        )

    def merge(self, other: "MetricGroupDefinition"):
        """Merge with another metric group definition."""
        for key in attr.fields_dict(type(self)):
            setattr(self, key, getattr(other, key) or getattr(self, key))


@attr.s(auto_attribs=True)
class MetricGroupsSpec:
    """Describes the interface for defining custom dimensions."""

    definitions: Dict[str, MetricGroupDefinition] = attr.Factory(dict)

    @classmethod
    def from_dict(cls, d: dict) -> "MetricGroupsSpec":
        """Create a `MetricGroupsSpec` from a dictionary."""
        d = dict((k.lower(), v) for k, v in d.items())

        definitions = {
            k: converter.structure({"name": k, **v}, MetricGroupDefinition) for k, v in d.items()
        }
        return cls(definitions=definitions)

    def merge(self, other: "MetricGroupsSpec"):
        """
        Merge another metric group spec into the current one.

        The `other` MetricGroupsSpec overwrites existing keys.
        """
        seen = []
        for key, _ in self.definitions.items():
            if key in other.definitions:
                self.definitions[key].merge(other.definitions[key])
            seen.append(key)
        for key, definition in other.definitions.items():
            if key not in seen:
                self.definitions[key] = definition


converter.register_structure_hook(
    MetricGroupsSpec, lambda obj, _type: MetricGroupsSpec.from_dict(obj)
)
