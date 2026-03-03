"""Config collection loading and shared state."""

import logging
from pathlib import Path

from metric_config_parser.config import ConfigCollection

logger = logging.getLogger(__name__)

_config_collection: ConfigCollection | None = None
_repo_path: Path | None = None


def get_config_collection() -> ConfigCollection:
    """Get or initialize the config collection."""
    global _config_collection, _repo_path

    if _config_collection is None:
        logger.info("Loading metric hub configs from GitHub")
        _config_collection = ConfigCollection.from_github_repo(
            "https://github.com/mozilla/metric-hub"
        )

    return _config_collection


def get_repo_path() -> Path:
    """Get the local repo path (used for reading/writing config files)."""
    if _repo_path is not None:
        return _repo_path
    return Path(__file__).parent.parent.parent.parent
