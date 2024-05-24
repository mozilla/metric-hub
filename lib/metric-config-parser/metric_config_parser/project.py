import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional

import attr

if TYPE_CHECKING:
    from metric_config_parser.config import ConfigCollection
    from metric_config_parser.monitoring import MonitoringSpec

from metric_config_parser.alert import AlertReference
from metric_config_parser.experiment import Experiment
from metric_config_parser.metric import MetricReference
from metric_config_parser.metric_group import MetricGroup, MetricGroupsSpec
from metric_config_parser.population import PopulationConfiguration, PopulationSpec
from metric_config_parser.util import converter, parse_date


class MonitoringPeriod(enum.Enum):
    """
    Monitoring period.

    Used as x-axis.
    """

    BUILD_ID = "build_id"
    DAY = "submission_date"


@attr.s(auto_attribs=True, kw_only=True)
class ProjectConfiguration:
    """Describes the interface for defining the project in configuration."""

    reference_branch: str = "control"
    app_name: str = "firefox_desktop"
    name: Optional[str] = None
    xaxis: MonitoringPeriod = attr.ib(default=MonitoringPeriod.DAY)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    population: PopulationConfiguration = attr.Factory(PopulationConfiguration)
    compact_visualization: bool = False
    skip_default_metrics: bool = False
    skip: bool = False
    is_rollout: bool = False
    metric_groups: List[MetricGroup] = attr.Factory(list)


def _validate_yyyy_mm_dd(instance: Any, attribute: Any, value: Any) -> None:
    parse_date(value)


@attr.s(auto_attribs=True, kw_only=True)
class ProjectSpec:
    """Describes the interface for defining the project."""

    name: Optional[str] = None
    platform: Optional[str] = None
    xaxis: Optional[MonitoringPeriod] = None
    start_date: Optional[str] = attr.ib(default=None, validator=_validate_yyyy_mm_dd)
    end_date: Optional[str] = attr.ib(default=None, validator=_validate_yyyy_mm_dd)
    metrics: List[MetricReference] = attr.Factory(list)
    alerts: List[AlertReference] = attr.Factory(list)
    reference_branch: Optional[str] = None
    population: PopulationSpec = attr.Factory(PopulationSpec)
    compact_visualization: bool = False
    skip_default_metrics: bool = False
    skip: bool = False
    is_rollout: bool = False
    metric_groups: MetricGroupsSpec = attr.Factory(MetricGroupsSpec)

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectSpec":
        """Create a new `ProjectSpec` from a dictionary."""
        d = dict((k.lower(), v) for k, v in d.items())
        return converter.structure(d, cls)

    def resolve(
        self,
        spec: "MonitoringSpec",
        experiment: Optional["Experiment"],
        configs: "ConfigCollection",
    ) -> ProjectConfiguration:
        """Create a `ProjectConfiguration` from the spec."""

        project_config = ProjectConfiguration(
            name=self.name or (experiment.normandy_slug if experiment else None),
            xaxis=self.xaxis or MonitoringPeriod.DAY,
            start_date=parse_date(
                self.start_date
                or (
                    experiment.start_date.strftime("%Y-%m-%d")
                    if experiment and experiment.start_date
                    else None
                )
            ),
            end_date=parse_date(
                self.end_date
                or (
                    experiment.end_date.strftime("%Y-%m-%d")
                    if experiment and experiment.end_date
                    else None
                )
            ),
            reference_branch=self.reference_branch
            or (
                experiment.reference_branch
                if experiment and experiment.reference_branch
                else "control"
            ),
            compact_visualization=self.compact_visualization,
            skip_default_metrics=self.skip_default_metrics,
            skip=self.skip,
            app_name=self.platform or "firefox_desktop",
            is_rollout=self.is_rollout,
            metric_groups=[],
        )
        project_config.population = self.population.resolve(spec, project_config, configs)

        metric_groups = []
        for group_ref in [d for _, d in self.metric_groups.definitions.items()]:
            metric_groups.append(group_ref.resolve(spec, project_config, configs))

        project_config.metric_groups = metric_groups

        return project_config

    def merge(self, other: "ProjectSpec") -> None:
        """
        Merge another project spec into the current one.

        The `other` ProjectSpec overwrites existing keys.
        """
        for key in attr.fields_dict(type(self)):
            if key == "population":
                self.population.merge(other.population)
            elif key == "metrics":
                self.metrics += other.metrics
            elif key == "alerts":
                self.alerts += other.alerts
            elif key == "metric_groups":
                self.metric_groups.merge(other.metric_groups)
            else:
                setattr(self, key, getattr(other, key) or getattr(self, key))
