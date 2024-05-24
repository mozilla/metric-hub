from typing import TYPE_CHECKING, Dict, Optional

import attr

if TYPE_CHECKING:
    from metric_config_parser.config import ConfigCollection
    from metric_config_parser.monitoring import MonitoringSpec
    from metric_config_parser.project import ProjectConfiguration

from metric_config_parser.data_source import DataSource, DataSourceReference
from metric_config_parser.util import converter


@attr.s(auto_attribs=True)
class Dimension:
    """Represents a dimension for segmenting client populations."""

    name: str
    data_source: DataSource
    select_expression: str
    friendly_name: Optional[str] = None
    description: Optional[str] = None


@attr.s(auto_attribs=True)
class DimensionDefinition:
    """Describes the interface for defining a dimension in configuration."""

    name: str  # implicit in configuration
    select_expression: str
    data_source: DataSourceReference
    friendly_name: Optional[str] = None
    description: Optional[str] = None

    def resolve(
        self, spec: "MonitoringSpec", conf: "ProjectConfiguration", configs: "ConfigCollection"
    ) -> Dimension:
        """Create and return a `Dimension` from the definition."""
        return Dimension(
            name=self.name,
            data_source=self.data_source.resolve(spec, conf, configs),
            select_expression=self.select_expression,
            friendly_name=self.friendly_name,
            description=self.description,
        )

    def merge(self, other: "DimensionDefinition"):
        """Merge with another dimension definition."""
        for key in attr.fields_dict(type(self)):
            setattr(self, key, getattr(other, key) or getattr(self, key))


@attr.s(auto_attribs=True)
class DimensionsSpec:
    """Describes the interface for defining custom dimensions."""

    definitions: Dict[str, DimensionDefinition] = attr.Factory(dict)

    @classmethod
    def from_dict(cls, d: dict) -> "DimensionsSpec":
        """Create a `DimensionsSpec` from a dictionary."""
        d = dict((k.lower(), v) for k, v in d.items())

        definitions = {
            k: converter.structure({"name": k, **v}, DimensionDefinition) for k, v in d.items()
        }
        return cls(definitions=definitions)

    def merge(self, other: "DimensionsSpec"):
        """
        Merge another dimension spec into the current one.

        The `other` DimensionsSpec overwrites existing keys.
        """
        seen = []
        for key, _ in self.definitions.items():
            if key in other.definitions:
                self.definitions[key].merge(other.definitions[key])
            seen.append(key)
        for key, definition in other.definitions.items():
            if key not in seen:
                self.definitions[key] = definition


converter.register_structure_hook(DimensionsSpec, lambda obj, _type: DimensionsSpec.from_dict(obj))


@attr.s(auto_attribs=True)
class DimensionReference:
    """Represents a reference to a dimension."""

    name: str

    def resolve(
        self, spec: "MonitoringSpec", conf: "ProjectConfiguration", configs: "ConfigCollection"
    ) -> Dimension:
        """Return the referenced `Dimension`."""
        if self.name in spec.dimensions.definitions:
            return spec.dimensions.definitions[self.name].resolve(spec, conf, configs)
        raise ValueError(f"Could not locate dimension {self.name}")


converter.register_structure_hook(
    DimensionReference, lambda obj, _type: DimensionReference(name=obj)
)
