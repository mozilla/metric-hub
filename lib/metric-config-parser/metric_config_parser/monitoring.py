import copy
from typing import TYPE_CHECKING, Any, List, Mapping, Optional

import attr

if TYPE_CHECKING:
    from metric_config_parser.config import ConfigCollection
    from metric_config_parser.definition import DefinitionSpecSub

from metric_config_parser.alert import Alert, AlertsSpec
from metric_config_parser.data_source import DataSourcesSpec
from metric_config_parser.dimension import Dimension, DimensionsSpec
from metric_config_parser.experiment import Experiment
from metric_config_parser.metric import MetricsSpec, Summary
from metric_config_parser.parameter import ParameterSpec
from metric_config_parser.project import ProjectConfiguration, ProjectSpec
from metric_config_parser.util import converter


@attr.s(auto_attribs=True)
class MonitoringConfiguration:
    """
    Represents configuration options.

    All references, for example to data sources, have been resolved in this representation.
    Instead of instantiating this directly, consider using MonitoringSpec.resolve().
    """

    project: Optional[ProjectConfiguration] = None
    metrics: List[Summary] = attr.Factory(list)
    dimensions: List[Dimension] = attr.Factory(list)
    alerts: List[Alert] = attr.Factory(list)


@attr.s(auto_attribs=True)
class MonitoringSpec:
    """
    Represents a configuration file.

    The expected use is like:
        MonitoringSpec.from_dict(toml.load(my_configuration_file)).resolve()
    which will produce a fully populated, concrete `MonitoringConfiguration`.
    """

    metrics: MetricsSpec = attr.Factory(MetricsSpec)
    data_sources: DataSourcesSpec = attr.Factory(DataSourcesSpec)
    project: ProjectSpec = attr.Factory(ProjectSpec)
    dimensions: DimensionsSpec = attr.Factory(DimensionsSpec)
    alerts: AlertsSpec = attr.Factory(AlertsSpec)
    parameters: ParameterSpec = attr.Factory(ParameterSpec)
    _resolved: bool = False

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "MonitoringSpec":
        """Create a `MonitoringSpec` from a dict."""
        d = dict((k.lower(), v) for k, v in d.items())
        return converter.structure(d, cls)

    @classmethod
    def from_definition_spec(
        cls,
        spec: "DefinitionSpecSub",
        project: Optional["ProjectSpec"] = None,
    ) -> "MonitoringSpec":
        from metric_config_parser.definition import DefinitionSpec

        if not isinstance(spec, MonitoringSpec) and not isinstance(spec, DefinitionSpec):
            raise ValueError(f"Cannot create MonitoringSpec from {spec}")

        if project is None:
            if isinstance(spec, MonitoringSpec):
                return cls(
                    metrics=spec.metrics,
                    data_sources=spec.data_sources,
                    dimensions=spec.dimensions,
                    alerts=spec.alerts,
                    parameters=spec.parameters,
                    project=spec.project,
                )
            else:
                return cls(
                    metrics=spec.metrics,
                    data_sources=spec.data_sources,
                    dimensions=spec.dimensions,
                    parameters=spec.parameters,
                )
        else:
            return cls(
                metrics=spec.metrics,
                data_sources=spec.data_sources,
                dimensions=spec.dimensions,
                alerts=spec.alerts,
                project=project,
                parameters=spec.parameters,
            )

    def resolve(
        self, experiment: Optional["Experiment"], configs: "ConfigCollection"
    ) -> MonitoringConfiguration:
        """Create a `MonitoringConfiguration` from the spec."""
        if self._resolved:
            raise Exception("Can't resolve an MonitoringSpec twice")

        self._resolved = True

        resolved_project = self.project.resolve(self, experiment, configs)

        # filter to only have metrics that actually need to be monitored
        metrics = []
        for metric_ref in {p.name for p in self.project.metrics}:
            if metric_ref in self.metrics.definitions:
                metrics += self.metrics.definitions[metric_ref].resolve(
                    self, resolved_project, configs
                )
            else:
                raise ValueError(f"No definition for metric {metric_ref}.")

        # filter to only have dimensions that actually are in use
        dimensions = []
        for dimension_ref in {d.name for d in self.project.population.dimensions}:
            if dimension_ref in self.dimensions.definitions:
                dimensions.append(
                    self.dimensions.definitions[dimension_ref].resolve(
                        self, resolved_project, configs
                    )
                )
            else:
                raise ValueError(f"No definition for dimension {dimension_ref}.")

        # filter to only have alerts that actually are in use
        alerts = []
        for alert_ref in {d.name for d in self.project.alerts}:
            if alert_ref in self.alerts.definitions:
                alerts.append(
                    self.alerts.definitions[alert_ref].resolve(self, resolved_project, configs)
                )
            else:
                raise ValueError(f"No definition for alert {alert_ref}.")

        return MonitoringConfiguration(
            project=resolved_project,
            metrics=metrics,
            dimensions=dimensions,
            alerts=alerts,
        )

    def merge(self, other: Optional["DefinitionSpecSub"]):
        """Merge another monitoring spec into the current one."""
        from metric_config_parser.definition import DefinitionSpec

        if other:
            if isinstance(other, MonitoringSpec):
                self.project.merge(other.project)
            if isinstance(other, MonitoringSpec) or isinstance(other, DefinitionSpec):
                self.dimensions.merge(other.dimensions)
            if isinstance(other, MonitoringSpec) or isinstance(other, DefinitionSpec):
                self.alerts.merge(other.alerts)
            self.data_sources.merge(other.data_sources)
            self.metrics.merge(other.metrics)

    @classmethod
    def default_for_platform_or_type(
        cls, platform: str, configs: "ConfigCollection"
    ) -> "MonitoringSpec":
        """Return the default config for the provided platform."""
        default_metrics = configs.get_platform_defaults(platform)

        if default_metrics is None or not hasattr(default_metrics, "project"):
            spec = cls()
        else:
            spec = cls.from_definition_spec(default_metrics)

        return copy.deepcopy(spec)
