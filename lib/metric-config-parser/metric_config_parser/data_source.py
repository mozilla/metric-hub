import fnmatch
import re
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import attr

from metric_config_parser.errors import DefinitionNotFound

if TYPE_CHECKING:
    from metric_config_parser.config import ConfigCollection
    from .experiment import ExperimentConfiguration
    from .definition import DefinitionSpecSub
    from .project import ProjectConfiguration

from . import AnalysisUnit
from .util import converter, is_valid_slug


class DataSourceJoinRelationship(Enum):
    ONE_TO_ONE = "one_to_one"
    MANY_TO_ONE = "many_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_MANY = "many_to_many"

    @staticmethod
    def from_str(label):
        match label:
            case "one_to_one":
                return DataSourceJoinRelationship.ONE_TO_ONE
            case "many_to_one":
                return DataSourceJoinRelationship.MANY_TO_ONE
            case "one_to_many":
                return DataSourceJoinRelationship.ONE_TO_MANY
            case "many_to_many":
                return DataSourceJoinRelationship.MANY_TO_MANY
            case _:
                raise NotImplementedError


@attr.s(auto_attribs=True)
class DataSourceJoin:
    data_source: "DataSource"
    relationship: Optional[DataSourceJoinRelationship]
    on_expression: Optional[str]


@attr.s(frozen=True, slots=True)
class DataSource:
    """Represents a table or view, from which Metrics may be defined.
    Args:
        name (str): Name for the Data Source. Used in sanity metric
            column names.
        from_expression (str): FROM expression - often just a fully-qualified
            table name. Sometimes a subquery. May contain the string
            ``{dataset}`` which will be replaced with an app-specific
            dataset for Glean apps. If the expression is templated
            on dataset, default_dataset is mandatory.
        experiments_column_type (str or None): Info about the schema
            of the table or view:
            * 'simple': There is an ``experiments`` column, which is an
              (experiment_slug:str -> branch_name:str) map.
            * 'native': There is an ``experiments`` column, which is an
              (experiment_slug:str -> struct) map, where the struct
              contains a ``branch`` field, which is the branch as a
              string.
            * 'glean': There is an ``experiments`` column inside ping_info,
              which is an (experiment_slug:str -> struct) map, where the
              struct contains a ``branch`` field, which is the branch as a
              string.
            * 'events_stream': There is an ``experiment`` within a JSON
              column ``event_extra``. ``branch`` is in the same column.
            * None: There is no ``experiments`` column, so skip the
              sanity checks that rely on it. We'll also be unable to
              filter out pre-enrollment data from day 0 in the
              experiment.
        client_id_column (str, optional): Name of the column that
            contains the ``client_id`` (join key). Defaults to
            'client_id'.
        submission_date_column (str, optional): Name of the column
            that contains the submission date (as a date, not
            timestamp). Defaults to 'submission_date'.
        default_dataset (str, optional): The value to use for
            `{dataset}` in from_expr if a value is not provided
            at runtime. Mandatory if from_expr contains a
            `{dataset}` parameter.
        build_id_column (str, optional):
            Default 'SAFE.SUBSTR(application.build_id, 0, 8)'.
        friendly_name (str, optional)
        description (str, optional)
        joins (list[DataSourceJoin], optional)
        columns_as_dimensions (bool, optional): Default false.
        analysis_units (list[AnalysisUnit], optional): denotes which
            aggregations are supported by this data_source. At time
            of writing, this means 'client_id', 'profile_group_id',
            or both. Defaults to both ['client_id', 'profile_group_id']
            for firefox_desktop, ['client_id'] otherwise.
        group_id_column (str, optional): Name of the column that
            contains the ``profile_group_id`` (join key). Defaults to
            'profile_group_id'.
        glean_client_id_column (str, optional): Name of the column that
            contains the *glean* telemetry ``client_id`` (join key).
            This is also used to specify that the data source supports glean.
        legacy_client_id_column (str, optional): Name of the column that
            contains the *legacy* telemetry ``client_id`` (join key).
            This is also used to specify that the data source supports legacy.
    """

    name = attr.ib(validator=attr.validators.instance_of(str))
    from_expression = attr.ib(validator=attr.validators.instance_of(str))
    experiments_column_type = attr.ib(default="simple", type=str)
    client_id_column = attr.ib(default=AnalysisUnit.CLIENT.value, type=str)
    submission_date_column = attr.ib(default="submission_date", type=str)
    default_dataset = attr.ib(default=None, type=Optional[str])
    build_id_column = attr.ib(default="SAFE.SUBSTR(application.build_id, 0, 8)", type=str)
    friendly_name = attr.ib(default=None, type=str)
    description = attr.ib(default=None, type=str)
    joins = attr.ib(default=None, type=List[DataSourceJoin])
    columns_as_dimensions = attr.ib(default=False, type=bool)
    analysis_units = attr.ib(default=[AnalysisUnit.CLIENT], type=List[AnalysisUnit])
    group_id_column = attr.ib(default=AnalysisUnit.PROFILE_GROUP.value, type=str)
    glean_client_id_column = attr.ib(default=None, type=str)
    legacy_client_id_column = attr.ib(default=None, type=str)

    EXPERIMENT_COLUMN_TYPES = (None, "simple", "native", "glean", "events_stream")

    @experiments_column_type.validator
    def _check_experiments_column_type(self, attribute, value):
        if value not in self.EXPERIMENT_COLUMN_TYPES:
            raise ValueError(
                f"experiments_column_type {repr(value)} must be one of: "
                f"{repr(self.EXPERIMENT_COLUMN_TYPES)}"
            )

    @default_dataset.validator
    def _check_default_dataset_provided_if_needed(self, attribute, value):
        self.from_expr_for(None)

    def from_expr_for(self, dataset: Optional[str]) -> str:
        """Expands the ``from_expression`` template for the given dataset.
        If ``from_expression`` is not a template, returns ``from_expression``.
        Args:
            dataset (str or None): Dataset name to substitute
                into the from expression.
        """
        effective_dataset = dataset or self.default_dataset
        if effective_dataset is None:
            try:
                return self.from_expression.format()
            except Exception as e:
                raise ValueError(
                    f"{self.name}: from_expression contains a dataset template but no value was provided."  # noqa:E501
                ) from e
        return self.from_expression.format(dataset=effective_dataset)


@attr.s(auto_attribs=True)
class DataSourceReference:
    name: str

    def resolve(
        self,
        spec: "DefinitionSpecSub",
        conf: Union["ExperimentConfiguration", "ProjectConfiguration"],
        configs: "ConfigCollection",
    ) -> DataSource:
        if self.name in spec.data_sources.definitions:
            return spec.data_sources.definitions[self.name].resolve(spec, conf, configs)

        data_source_definition = configs.get_data_source_definition(self.name, conf.app_name)
        if data_source_definition is None:
            raise DefinitionNotFound(f"No default definition for data source '{self.name}' found")
        return data_source_definition.resolve(spec, conf, configs)


converter.register_structure_hook(
    DataSourceReference, lambda obj, _type: DataSourceReference(name=obj)
)


@attr.s(auto_attribs=True)
class DataSourceDefinition:
    """Describes the interface for defining a data source in configuration."""

    name: str  # implicit in configuration
    from_expression: Optional[str] = None
    experiments_column_type: Optional[str] = None
    client_id_column: Optional[str] = None
    submission_date_column: Optional[str] = None
    default_dataset: Optional[str] = None
    build_id_column: Optional[str] = None
    friendly_name: Optional[str] = None
    description: Optional[str] = None
    joins: Optional[Dict[str, Dict[str, Any]]] = None
    columns_as_dimensions: Optional[bool] = None
    analysis_units: Optional[list[AnalysisUnit]] = None
    group_id_column: Optional[str] = None
    glean_client_id_column: Optional[str] = None
    legacy_client_id_column: Optional[str] = None

    def resolve(
        self,
        spec: "DefinitionSpecSub",
        conf: Union["ExperimentConfiguration", "ProjectConfiguration"],
        configs: "ConfigCollection",
    ) -> DataSource:
        if not is_valid_slug(self.name):
            # a data source name cannot include a wildcard * because if
            # it does at this point in the code,
            # that means it isn't defined anywhere and there's some dangling wildcard
            raise ValueError(
                f"Invalid identifier found in name {self.name}. "
                + "Name must at least consist of one character, number or underscore. "
                + "Wildcard characters are only allowed if matching slug is defined."
            )

        default_analysis_units = [AnalysisUnit.CLIENT]
        app_name = ""
        if getattr(conf, "app_name", None):
            if TYPE_CHECKING:
                assert isinstance(conf, ProjectConfiguration)
            app_name = conf.app_name
        elif getattr(conf, "experiment", None):
            if TYPE_CHECKING:
                assert isinstance(conf, ExperimentConfiguration)
            app_name = conf.experiment.app_name

        if app_name == "firefox_desktop":
            default_analysis_units.append(AnalysisUnit.PROFILE_GROUP)

        params: Dict[str, Any] = {
            "name": self.name,
            "from_expression": self.from_expression,
        }
        # Allow mozanalysis to infer defaults for these values:
        for k in (
            "experiments_column_type",
            "client_id_column",
            "submission_date_column",
            "default_dataset",
            "build_id_column",
            "friendly_name",
            "description",
            "columns_as_dimensions",
            "analysis_units",
            "group_id_column",
            "glean_client_id_column",
            "legacy_client_id_column",
        ):
            v = getattr(self, k)
            # analysis_units is special: its default value is based on the app_name
            # so we'll set it to default_analysis_units if it isn't already set
            if k == "analysis_units":
                params[k] = v or default_analysis_units
            elif v:
                params[k] = v
        # experiments_column_type is a little special, though!
        # `None` is a valid value, which means there isn't any `experiments` column in the
        # data source, so mozanalysis shouldn't try to use it.
        # But mozanalysis has a different default value for that param ("simple"), and
        # TOML can't represent an explicit null. So we'll look for the string "none" and
        # transform it to the value None.
        if (self.experiments_column_type or "").lower() == "none":
            params["experiments_column_type"] = None

        # resolve the data source joins
        if self.joins and len(self.joins) > 0:
            params["joins"] = [
                DataSourceJoin(
                    data_source=DataSourceReference(name=data_source).resolve(spec, conf, configs),
                    relationship=(
                        DataSourceJoinRelationship.from_str(join["relationship"])
                        if "relationship" in join
                        else None
                    ),
                    on_expression=join.get("on_expression", None),
                )
                for data_source, join in self.joins.items()
            ]

        return DataSource(**params)

    def merge(self, other: "DataSourceDefinition"):
        """Merge with another data source definition."""
        for key in attr.fields_dict(type(self)):
            if key != "name":
                setattr(self, key, getattr(other, key) or getattr(self, key))
            if key == "joins":
                if getattr(other, key) is not None:
                    setattr(self, key, getattr(other, key))


@attr.s(auto_attribs=True)
class DataSourcesSpec:
    """Holds data source definitions.

    This doesn't have a resolve() method to produce a concrete DataSourcesConfiguration
    because it's just a container for the definitions, and we don't need it after the spec phase.
    """

    definitions: Dict[str, DataSourceDefinition] = attr.Factory(dict)

    @classmethod
    def from_dict(cls, d: dict) -> "DataSourcesSpec":
        definitions = {
            k: converter.structure(
                {"name": k, **dict((kk.lower(), vv) for kk, vv in v.items())},
                DataSourceDefinition,
            )
            for k, v in d.items()
        }
        return cls(definitions)

    def merge(self, other: "DataSourcesSpec"):
        """
        Merge another datasource spec into the current one.
        The `other` DataSourcesSpec overwrites existing keys.
        """
        seen = set()
        for key, _ in self.definitions.items():
            for other_key in other.definitions:
                # support wildcard characters in `other`
                other_key_regex = re.compile(fnmatch.translate(other_key))
                if other_key_regex.fullmatch(key):
                    self.definitions[key].merge(other.definitions[other_key])
                    seen.add(other_key)
            seen.add(key)
        for key, definition in other.definitions.items():
            if key not in seen and is_valid_slug(key):
                self.definitions[key] = definition


converter.register_structure_hook(
    DataSourcesSpec, lambda obj, _type: DataSourcesSpec.from_dict(obj)
)
