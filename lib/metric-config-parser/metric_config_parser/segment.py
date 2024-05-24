from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Optional

import attr
import jinja2
from jinja2 import StrictUndefined

if TYPE_CHECKING:
    from .config import ConfigCollection
    from .analysis import AnalysisSpec
    from .experiment import ExperimentConfiguration

from .errors import DefinitionNotFound
from .util import converter


@attr.s(frozen=True, slots=True)
class SegmentDataSource:
    """Represents a table or view, from which segments may be defined.
    ``window_start`` and ``window_end`` define the window of data used
    to determine whether each client fits a segment. Ideally this
    window ends at/before the moment of enrollment, so that user's
    branches can't bias the segment assignment. ``window_start`` and
    ``window_end`` are integers, representing the number
    of days before or after enrollment.
    Args:
        name (str): Name for the Data Source. Should be unique to avoid
            confusion.
        from_expression (str): FROM expression - often just a fully-qualified
            table name. Sometimes a subquery. May contain the string
            ``{dataset}`` which will be replaced with an app-specific
            dataset for Glean apps. If the expression is templated
            on dataset, default_dataset is mandatory.
        window_start (int, optional): See above.
        window_end (int, optional): See above.
        client_id_column (str, optional): Name of the column that
            contains the ``client_id`` (join key). Defaults to
            'client_id'.
        submission_date_column (str, optional): Name of the column
            that contains the submission date (as a date, not
            timestamp). Defaults to 'submission_date'.
        default_dataset (str, optional): The value to use for
            `{dataset}` in from_expression if a value is not provided
            at runtime. Mandatory if from_expression contains a
            `{dataset}` parameter.
    """

    name = attr.ib(validator=attr.validators.instance_of(str))
    from_expression = attr.ib(validator=attr.validators.instance_of(str))
    window_start = attr.ib(default=0, type=int)
    window_end = attr.ib(default=0, type=int)
    client_id_column = attr.ib(default="client_id", type=str)
    submission_date_column = attr.ib(default="submission_date", type=str)
    default_dataset = attr.ib(default=None, type=Optional[str])


@attr.s(frozen=True, slots=True)
class Segment:
    """Represents an experiment Segment.
    Args:
        name (str): The segment's name; will be a column name.
        data_source (SegmentDataSource): Data source that provides
            the columns referenced in ``select_expression``.
        select_expression (str): A SQL select expression that includes
            an aggregation function (we ``GROUP BY client_id``).
            Returns a non-NULL ``BOOL``: ``True`` if the user is in the
            segment, ``False`` otherwise.
        friendly_name (str): A human-readable dashboard title for this segment
        description (str): A paragraph of Markdown-formatted text describing
            the segment in more detail, to be shown on dashboards
    """

    name = attr.ib(type=str)
    data_source = attr.ib(validator=attr.validators.instance_of(SegmentDataSource))
    select_expression = attr.ib(type=str)
    friendly_name = attr.ib(type=Optional[str], default=None)
    description = attr.ib(type=Optional[str], default=None)


@attr.s(auto_attribs=True)
class SegmentReference:
    name: str

    def resolve(
        self,
        spec: "AnalysisSpec",
        conf: "ExperimentConfiguration",
        configs: "ConfigCollection",
    ) -> Segment:
        if self.name in spec.segments.definitions:
            return spec.segments.definitions[self.name].resolve(spec, conf, configs)
        segment_definition = configs.get_segment_definition(self.name, conf.app_name)
        if segment_definition is None:
            raise DefinitionNotFound(f"Could not find definition for segment '{self.name}'")
        return segment_definition.resolve(spec, conf, configs)


converter.register_structure_hook(SegmentReference, lambda obj, _type: SegmentReference(name=obj))


@attr.s(auto_attribs=True)
class SegmentDataSourceDefinition:
    name: str
    from_expression: str
    window_start: int = 0
    window_end: int = 0
    client_id_column: Optional[str] = "client_id"
    submission_date_column: Optional[str] = "submission_date"
    default_dataset: Optional[str] = None

    def resolve(
        self,
        spec: "AnalysisSpec",
        conf: "ExperimentConfiguration",
        _configs: "ConfigCollection",
    ) -> SegmentDataSource:
        env = jinja2.Environment(autoescape=False, undefined=StrictUndefined)
        from_expression = env.from_string(self.from_expression).render(experiment=conf)
        kwargs: Dict[str, Any] = {
            "name": self.name,
            "from_expression": from_expression,
            "window_start": self.window_start,
            "window_end": self.window_end,
        }
        for k in ("client_id_column", "submission_date_column"):
            v = getattr(self, k)
            if v:
                kwargs[k] = v
        return SegmentDataSource(**kwargs)


@attr.s(auto_attribs=True)
class SegmentDataSourceReference:
    name: str

    def resolve(
        self,
        spec: "AnalysisSpec",
        conf: "ExperimentConfiguration",
        configs: "ConfigCollection",
    ) -> SegmentDataSource:
        if self.name in spec.segments.data_sources:
            return spec.segments.data_sources[self.name].resolve(spec, conf, configs)
        segment_definition = configs.get_segment_data_source_definition(self.name, conf.app_name)
        if segment_definition is None:
            raise DefinitionNotFound(
                f"Could not find definition for segment data source '{self.name}'"
            )
        return segment_definition.resolve(spec, conf, configs)


converter.register_structure_hook(
    SegmentDataSourceReference, lambda obj, _type: SegmentDataSourceReference(name=obj)
)


@attr.s(auto_attribs=True)
class SegmentDefinition:
    name: str
    data_source: SegmentDataSourceReference
    select_expression: str
    friendly_name: Optional[str] = None
    description: Optional[str] = None

    def resolve(
        self,
        spec: "AnalysisSpec",
        conf: "ExperimentConfiguration",
        configs: "ConfigCollection",
    ) -> Segment:
        data_source = self.data_source.resolve(spec, conf, configs)

        return Segment(
            name=self.name,
            data_source=data_source,
            select_expression=configs.get_env().from_string(self.select_expression).render(),
            friendly_name=dedent(self.friendly_name) if self.friendly_name else self.friendly_name,
            description=dedent(self.description) if self.description else self.description,
        )


@attr.s(auto_attribs=True)
class SegmentsSpec:
    definitions: Dict[str, SegmentDefinition] = attr.Factory(dict)
    data_sources: Dict[str, SegmentDataSourceDefinition] = attr.Factory(dict)

    @classmethod
    def from_dict(cls, d: dict) -> "SegmentsSpec":
        data_sources = {
            k: converter.structure(
                {"name": k, **dict((kk.lower(), vv) for kk, vv in v.items())},
                SegmentDataSourceDefinition,
            )
            for k, v in d.pop("data_sources", {}).items()
        }
        definitions = {
            k: converter.structure(
                {"name": k, **dict((kk.lower(), vv) for kk, vv in v.items())}, SegmentDefinition
            )
            for k, v in d.items()
        }
        return cls(definitions, data_sources)

    def merge(self, other: "SegmentsSpec"):
        """
        Merge another segments spec into the current one.
        The `other` SegmentsSpec overwrites existing keys.
        """
        self.data_sources.update(other.data_sources)
        self.definitions.update(other.definitions)


converter.register_structure_hook(SegmentsSpec, lambda obj, _type: SegmentsSpec.from_dict(obj))
