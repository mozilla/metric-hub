from functools import partial
from typing import Any, Callable, Dict, Mapping, Optional

import attr


@attr.s(auto_attribs=True)
class Function:
    slug: str
    definition: Callable
    friendly_name: Optional[str] = None
    description: Optional[str] = None


@attr.s(auto_attribs=True)
class FunctionsSpec:
    functions: Dict[str, Function]

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
                    friendly_name=fun["friendly_name"] if "friendly_name" in fun else None,
                    description=fun["description"] if "description" in fun else None,
                )
                for slug, fun in d["functions"].items()
            }
        )
