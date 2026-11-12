from typing import TYPE_CHECKING

import attr

from .analysis import AnalysisSpec
from .config import ConfigCollection
from .project import ProjectConfiguration

if TYPE_CHECKING:
    from .segment import Segment


@attr.s(auto_attribs=True, frozen=True)
class SegmentSource:
    data_source: str
    from_expression: str
    window_start: int
    window_end: int
    client_id_column: str
    group_id_column: str
    submission_date_column: str


@attr.s(auto_attribs=True, frozen=True)
class SegmentMetric:
    name: str
    data_source: str
    select_expression: str


@attr.s(auto_attribs=True, frozen=True)
class SegmentPlan:
    sources: dict[str, SegmentSource]
    segments: dict[str, SegmentMetric]
    missing: list[str]


def segment_plan(configs: ConfigCollection, app_name: str, segment_names: list[str]) -> SegmentPlan:
    missing: list[str] = []
    resolved: list[tuple[str, Segment]] = []
    project = ProjectConfiguration(app_name=app_name)
    for name in sorted(segment_names):
        segment_definition = configs.get_segment_definition(name, app_name)
        if segment_definition is None:
            missing.append(name)
        else:
            resolved.append(
                (name, segment_definition.resolve(AnalysisSpec(), project, configs))  # type: ignore
            )

    sources = {
        segment.data_source.name: SegmentSource(
            data_source=segment.data_source.name,
            from_expression=segment.data_source.from_expression,
            window_start=segment.data_source.window_start,
            window_end=segment.data_source.window_end,
            client_id_column=segment.data_source.client_id_column,
            group_id_column=segment.data_source.group_id_column,
            submission_date_column=segment.data_source.submission_date_column,
        )
        for _, segment in resolved
    }

    segments = {
        name: SegmentMetric(
            name=name,
            data_source=segment.data_source.name,
            select_expression=segment.select_expression,
        )
        for name, segment in resolved
    }

    return SegmentPlan(sources=sources, segments=segments, missing=missing)
