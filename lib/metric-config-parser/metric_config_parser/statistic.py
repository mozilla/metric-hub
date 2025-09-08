from typing import Any

import attr


@attr.s(auto_attribs=True)
class Statistic:
    name: str
    params: dict[str, Any]
