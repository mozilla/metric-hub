import enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import attr

if TYPE_CHECKING:
    from metric_config_parser.config import ConfigCollection
    from metric_config_parser.monitoring import MonitoringSpec
    from metric_config_parser.definition import DefinitionSpecSub
    from metric_config_parser.project import ProjectConfiguration

from metric_config_parser.metric import MetricReference, Summary
from metric_config_parser.util import converter


# todo: probably should just be a string
class AlertType(enum.Enum):
    """Different types of alerts."""

    # alert when confidence intervals of different branches don't overlap
    CI_OVERLAP = "ci_overlap"

    # alert if defined thresholds are exceeded/too low
    THRESHOLD = "threshold"

    # alert if average of most recent measurement window is below/above average of previous window
    AVG_DIFF = "avg_diff"


@attr.s(auto_attribs=True)
class Alert:
    """Represents an alert."""

    name: str
    type: AlertType
    metrics: List[Summary]
    friendly_name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[List[Any]] = []
    min: Optional[List[int]] = None
    max: Optional[List[int]] = None
    window_size: Optional[int] = None
    max_relative_change: Optional[float] = None
    statistics: Optional[List[str]] = None


@attr.s(auto_attribs=True)
class AlertReference:
    """Represents a reference to an alert."""

    name: str

    def resolve(
        self, spec: "DefinitionSpecSub", conf: "ProjectConfiguration", configs: "ConfigCollection"
    ) -> Alert:
        """Return the `Alert` that this is referencing."""
        if isinstance(spec, MonitoringSpec):
            if self.name not in spec.alerts.definitions:
                raise ValueError(f"Alert {self.name} has not been defined.")

            return spec.alerts.definitions[self.name].resolve(spec, conf, configs)
        else:
            raise ValueError(f"Alerts cannot be defined as part of {spec}")


converter.register_structure_hook(AlertReference, lambda obj, _type: AlertReference(name=obj))


@attr.s(auto_attribs=True)
class AlertDefinition:
    """Describes the interface for defining an alert in configuration."""

    name: str  # implicit in configuration
    type: AlertType
    metrics: List[MetricReference]
    friendly_name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[List[Any]] = None
    min: Optional[List[int]] = None
    max: Optional[List[int]] = None
    window_size: Optional[int] = None
    max_relative_change: Optional[float] = None
    statistics: Optional[List[str]] = None

    def __attrs_post_init__(self):
        """Validate that the right parameters have been set depending on the alert type."""
        if self.type == AlertType.CI_OVERLAP:
            none_fields = ["min", "max", "window_size", "max_relative_change"]
        elif self.type == AlertType.THRESHOLD:
            none_fields = ["window_size", "max_relative_change"]
            if self.min is None and self.max is None:
                raise ValueError(
                    "Either 'max' or 'min' needs to be set when defining a threshold alert"
                )
            if self.min and self.parameters and len(self.min) != len(self.parameters):
                raise ValueError(
                    "Number of 'min' thresholds not matching number of parameters to monitor. "
                    + "A 'min' threshold needs to be specified for each percentile."
                )
            if self.max and self.parameters and len(self.max) != len(self.parameters):
                raise ValueError(
                    "Number of 'max' thresholds not matching number of parameters to monitor. "
                    + "A 'max' threshold needs to be specified for each percentile."
                )
        elif self.type == AlertType.AVG_DIFF:
            none_fields = ["min", "max"]
            if self.window_size is None:
                raise ValueError("'window_size' needs to be specified when using avg_diff alert")
            if self.max_relative_change is None:
                raise ValueError("'max_relative_change' to be specified when using avg_diff alert")

        for field in none_fields:
            if getattr(self, field) is not None:
                raise ValueError(
                    f"For alert of type {str(self.type)}, the parameter {field} must not be set"
                )

    def resolve(
        self, spec: "DefinitionSpecSub", conf: "ProjectConfiguration", configs: "ConfigCollection"
    ) -> Alert:
        """Create and return a `Alert` from the definition."""
        # filter to only have metrics that actually need to be monitored
        metrics = []
        for metric_ref in {p.name for p in self.metrics}:
            if metric_ref in spec.metrics.definitions:
                metrics += spec.metrics.definitions[metric_ref].resolve(spec, conf, configs)
            else:
                raise ValueError(f"No definition for metric {metric_ref}.")

        return Alert(
            name=self.name,
            type=self.type,
            metrics=metrics,
            friendly_name=self.friendly_name,
            description=self.description,
            parameters=self.parameters,
            min=self.min,
            max=self.max,
            window_size=self.window_size,
            max_relative_change=self.max_relative_change,
            statistics=self.statistics,
        )


@attr.s(auto_attribs=True)
class AlertsSpec:
    """Describes the interface for defining custom alerts."""

    definitions: Dict[str, AlertDefinition] = attr.Factory(dict)

    @classmethod
    def from_dict(cls, d: dict) -> "AlertsSpec":
        """Create a `AlertsSpec` from a dictionary."""
        d = dict((k.lower(), v) for k, v in d.items())

        definitions = {
            k: converter.structure({"name": k, **v}, AlertDefinition) for k, v in d.items()
        }
        return cls(definitions=definitions)

    def merge(self, other: "AlertsSpec"):
        """
        Merge another alert spec into the current one.

        The `other` AlertsSpec overwrites existing keys.
        """
        for alert_name, alert_definition in other.definitions.items():
            if alert_name in self.definitions:
                for key in attr.fields_dict(type(self.definitions[alert_name])):
                    if key == "metrics":
                        self.definitions[alert_name].metrics += alert_definition.metrics
                    else:
                        setattr(
                            self.definitions[alert_name],
                            key,
                            getattr(alert_definition, key)
                            or getattr(self.definitions[alert_name], key),
                        )
            else:
                self.definitions[alert_name] = alert_definition

        self.definitions.update(other.definitions)


converter.register_structure_hook(AlertsSpec, lambda obj, _type: AlertsSpec.from_dict(obj))
