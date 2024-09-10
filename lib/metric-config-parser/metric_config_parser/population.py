from typing import TYPE_CHECKING, List, Optional

import attr

if TYPE_CHECKING:
    from metric_config_parser.config import ConfigCollection
    from metric_config_parser.monitoring import MonitoringSpec
    from metric_config_parser.project import ProjectConfiguration

from metric_config_parser.data_source import DataSource, DataSourceReference
from metric_config_parser.dimension import Dimension, DimensionReference
from metric_config_parser.experiment import Channel


@attr.s(auto_attribs=True, kw_only=True)
class PopulationConfiguration:
    """Describes the interface for defining the client population in configuration."""

    data_source: Optional[DataSource] = None
    boolean_pref: Optional[str] = None
    channel: Optional[Channel] = None
    branches: List[str] = attr.Factory(list)
    monitor_entire_population: bool = False
    group_by_dimension: Optional[Dimension] = None


@attr.s(auto_attribs=True, kw_only=True)
class PopulationSpec:
    """Describes the interface for defining the client population."""

    data_source: Optional[DataSourceReference] = None
    boolean_pref: Optional[str] = None
    channel: Optional[Channel] = None
    branches: Optional[List[str]] = None
    dimensions: List[DimensionReference] = attr.Factory(list)
    monitor_entire_population: bool = False
    group_by_dimension: Optional[DimensionReference] = None

    def resolve(
        self,
        spec: "MonitoringSpec",
        conf: "ProjectConfiguration",
        configs: "ConfigCollection",
    ) -> PopulationConfiguration:
        """Create a `PopulationConfiguration` from the spec."""
        if self.group_by_dimension:
            if self.group_by_dimension not in self.dimensions:
                raise ValueError(
                    f"{self.group_by_dimension} not listed as dimension, but used for grouping"
                )

        return PopulationConfiguration(
            data_source=(
                self.data_source.resolve(spec, conf, configs) if self.data_source else None
            ),
            boolean_pref=self.boolean_pref
            or (conf.population.boolean_pref if conf and not conf.is_rollout else None),
            channel=self.channel or (conf.population.channel if conf else None),
            branches=(
                self.branches
                if self.branches is not None
                else (
                    [branch for branch in conf.population.branches]
                    if conf and self.boolean_pref is None and not conf.is_rollout
                    else []
                )
            ),
            monitor_entire_population=self.monitor_entire_population,
            group_by_dimension=(
                self.group_by_dimension.resolve(spec, conf, configs)
                if self.group_by_dimension
                else None
            ),
        )

    def merge(self, other: "PopulationSpec") -> None:
        """
        Merge another population spec into the current one.

        The `other` PopulationSpec overwrites existing keys.
        """
        for key in attr.fields_dict(type(self)):
            if key == "branches":
                self.branches = self.branches if self.branches is not None else other.branches
            elif key == "dimensions":
                self.dimensions += other.dimensions
            else:
                setattr(self, key, getattr(other, key) or getattr(self, key))
