import re
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import cattr
import pytz

converter = cattr.Converter()


@contextmanager
def TemporaryDirectory():
    name = Path(tempfile.mkdtemp())
    try:
        yield name
    finally:
        if name.exists():
            shutil.rmtree(name)


def parse_date(yyyy_mm_dd: Optional[str]) -> Optional[datetime]:
    if not yyyy_mm_dd:
        return None
    return datetime.strptime(yyyy_mm_dd, "%Y-%m-%d").replace(tzinfo=pytz.utc)


def is_valid_slug(slug: str) -> bool:
    """Returns whether a slug name is valid."""
    return bool(re.match(r"^[a-zA-Z0-9_]+$", slug))
