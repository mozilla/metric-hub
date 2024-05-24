import enum
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Type, Union

import attr

if TYPE_CHECKING:
    from .config import ConfigCollection
    from .analysis import AnalysisSpec
    from .experiment import ExperimentConfiguration

from .data_source import DataSource, DataSourceReference
from .util import converter


class AnalysisWindow(enum.Enum):
    """
    Predefined timelimits that can be used for defining when exposures
    should be computed.
    """

    ANALYSIS_WINDOW_START = "analysis_window_start"
    ANALYSIS_WINDOW_END = "analysis_window_end"
    ENROLLMENT_START = "enrollment_start"
    ENROLLMENT_END = "enrollment_end"


WindowLimit = Union[int, AnalysisWindow, None]


def structure_window_limit(value: Any, _klass: Type) -> WindowLimit:
    try:
        return AnalysisWindow(value)
    except Exception:
        return int(value)


converter.register_structure_hook(WindowLimit, structure_window_limit)


@attr.s(auto_attribs=True, frozen=True, slots=True)
class ExposureSignal:
    """
    Jetstream exposure signal representation.

    Jetstream exposure signals are supersets of mozanalysis exposure signals
    with some additional metdata required for analysis.
    """

    name: str
    data_source: DataSource
    select_expression: str
    friendly_name: str
    description: str
    window_start: WindowLimit = attr.ib(None)
    window_end: WindowLimit = attr.ib(None)

    @window_end.validator
    @window_start.validator
    def validate_window(self, _attribute, value):
        if value is not None and not isinstance(value, int):
            AnalysisWindow(value)


@attr.s(auto_attribs=True)
class ExposureSignalDefinition:
    """Describes the interface for defining an exposure signal in configuration."""

    name: str
    data_source: DataSourceReference
    select_expression: str
    friendly_name: str
    description: str
    window_start: WindowLimit = None
    window_end: WindowLimit = None

    def resolve(
        self,
        spec: "AnalysisSpec",
        conf: "ExperimentConfiguration",
        configs: "ConfigCollection",
    ) -> ExposureSignal:
        return ExposureSignal(
            name=self.name,
            data_source=self.data_source.resolve(spec, conf=conf, configs=configs),
            select_expression=self.select_expression,
            friendly_name=dedent(self.friendly_name) if self.friendly_name else self.friendly_name,
            description=dedent(self.description) if self.description else self.description,
            window_start=self.window_start,
            window_end=self.window_end,
        )
