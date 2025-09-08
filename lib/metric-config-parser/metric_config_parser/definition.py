from collections.abc import Mapping
from typing import Any

import attr

from metric_config_parser.analysis import AnalysisSpec
from metric_config_parser.monitoring import MonitoringSpec

from .alert import AlertsSpec
from .data_source import DataSourcesSpec
from .dimension import DimensionsSpec
from .metric import MetricsSpec
from .parameter import ParameterSpec
from .segment import SegmentsSpec
from .util import converter


@attr.s(auto_attribs=True)
class DefinitionSpec:
    """A representation of a collection of definitions."""

    metrics: MetricsSpec = attr.Factory(MetricsSpec)
    data_sources: DataSourcesSpec = attr.Factory(DataSourcesSpec)
    segments: SegmentsSpec = attr.Factory(SegmentsSpec)
    dimensions: DimensionsSpec = attr.Factory(DimensionsSpec)
    alerts: AlertsSpec = attr.Factory(AlertsSpec)
    parameters: ParameterSpec = attr.Factory(ParameterSpec)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "DefinitionSpec":
        return converter.structure(d, cls)

    def merge(self, other: "DefinitionSpecSub"):
        self.metrics.merge(other.metrics)
        self.data_sources.merge(other.data_sources)
        if isinstance(other, DefinitionSpec | AnalysisSpec):
            self.segments.merge(other.segments)
        if isinstance(other, DefinitionSpec | MonitoringSpec):
            self.dimensions.merge(other.dimensions)
        if isinstance(other, DefinitionSpec | MonitoringSpec):
            self.alerts.merge(other.alerts)


DefinitionSpecSub = AnalysisSpec | MonitoringSpec | DefinitionSpec
