from typing import TYPE_CHECKING, Any

import attr

if TYPE_CHECKING:
    from .definition import DefinitionSpecSub


@attr.s(auto_attribs=True)
class PreTreatmentReference:
    name: str
    args: dict[str, Any]

    def resolve(self, spec: "DefinitionSpecSub") -> "PreTreatmentReference":
        return self
