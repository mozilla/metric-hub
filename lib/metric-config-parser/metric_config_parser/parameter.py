from collections import defaultdict
from typing import Any, Dict, Mapping, Optional, Union

import attr

from .errors import InvalidConfigurationException
from .util import converter


@attr.s(auto_attribs=True)
class ParameterDefinition:
    """
    * distinct_by_branch * indicates whether value for the parameter
        needs to be specified for each branch
        or if the value can be applied across all configuration branches (default: False)
    """

    name: str  # implicit in configuration
    friendly_name: Optional[str] = None
    description: Optional[str] = None
    value: Optional[Union[str, Dict[str, str]]] = None
    distinct_by_branch: Optional[bool] = False
    default: Optional[Union[str, Dict[str, Any]]] = None

    def validate(self) -> "ParameterDefinition":
        """
        Validates that branch related configuration is correct.

        It should not run on every instance of ParameterDefinition object.
        Outcome parameters containing defaults would not always adhere to
        the rules defined here.
        """

        if self.distinct_by_branch and not (
            isinstance(self.value, dict) or isinstance(self.default, dict)
        ):
            error_msg = (
                f"Parameter {self.name} configured "
                "to be distinct by branch, a mapping expected in the following format: "
                'for values: value.branch_1 = "1"'
                'and defaults: default.branch_1 = "1"'
                "See https://experimenter.info/jetstream/outcomes#parameterizing-outcomes for more information"  # noqa: E501
            )
            raise InvalidConfigurationException(error_msg)

        elif not self.distinct_by_branch and not (
            isinstance(self.value, str) or isinstance(self.default, str)
        ):
            error_msg = (
                f"Parameter {self.name} configured "
                "to not be distinct by branch, but wrong value type provided. "
                "Expected format: "
                f'value = "param_value", provided: {self.value}'
                f'default = "", provided: {self.default}'
                "See https://experimenter.info/jetstream/outcomes#parameterizing-outcomes for more information"  # noqa: E501
            )
            raise InvalidConfigurationException(error_msg)

        return self


converter.register_structure_hook(
    ParameterDefinition, lambda obj, _type: ParameterDefinition(**obj)
)


@attr.s(auto_attribs=True)
class ParameterSpec:
    """
    Object for holding definitions of all parameters.
    """

    definitions: Dict[str, ParameterDefinition] = attr.Factory(dict)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ParameterSpec":
        """
        Converts a dictionary object containing parameter configuration
        into a ParameterSpec Object that contains a ParameterDefinition
        for each parameter.

        """

        params: Dict[str, Any] = {"definitions": defaultdict()}

        for param_name, param_config in d.items():
            params["definitions"][param_name] = converter.structure(
                {"name": param_name, **dict((kk.lower(), vv) for kk, vv in param_config.items())},
                ParameterDefinition,
            )

        return cls(**params)


converter.register_structure_hook(ParameterSpec, lambda obj, _type: ParameterSpec.from_dict(obj))
