from collections.abc import Callable, Mapping
from functools import partial
from typing import Any

import attr


@attr.s(auto_attribs=True)
class Function:
    slug: str
    definition: Callable
    friendly_name: str | None = None
    description: str | None = None


@attr.s(auto_attribs=True)
class FunctionsSpec:
    functions: dict[str, Function]

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "FunctionsSpec":
        return cls(
            {
                slug: Function(
                    slug=slug,
                    definition=(
                        partial(
                            lambda select_expr, definition: definition.format(
                                select_expr=select_expr
                            ),
                            definition=fun["definition"],
                        )
                    ),
                    friendly_name=(fun.get("friendly_name", None)),
                    description=fun.get("description", None),
                )
                for slug, fun in d["functions"].items()
            }
        )
