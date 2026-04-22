"""Spec for Nimbus feature monitoring (featmon) TOML configs.

Config files live in the ``featmon/`` directory of a metric-hub repository
checkout, with one TOML file per application (e.g. ``firefox_desktop.toml``).

Each file defines:
- ``data_sources``: BigQuery tables to query, each with a ``type`` of
  ``"metrics"``, ``"event_stream"``, or ``"clients_daily"``
- ``features``: Nimbus features and the metrics to collect per source table

The ``dataset`` is derived from the filename stem (e.g. ``firefox_desktop.toml``
→ ``firefox_desktop``).
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import attr
import toml

VALID_SOURCE_TYPES = frozenset({"metrics", "event_stream", "clients_daily"})

FEATMON_DIR = "featmon"


@attr.s(auto_attribs=True)
class SourceTableSpec:
    """Represents a single BigQuery data source in a featmon config."""

    name: str
    table_name: str
    type: str = "metrics"
    analysis_unit_id: str = "client_info.client_id"
    dimensions: dict[str, Any] = attr.Factory(dict)


@attr.s(auto_attribs=True)
class FeatureSpec:
    """Represents a single Nimbus feature in a featmon config."""

    name: str
    slug: str | None = None
    metrics_by_source: dict[str, Any] = attr.Factory(dict)

    def nimbus_slug(self) -> str:
        """Return the Nimbus slug for this feature.

        Uses ``slug`` if explicitly set (needed when the Nimbus slug contains
        hyphens that are invalid as TOML keys), otherwise falls back to ``name``.
        """
        return self.slug if self.slug is not None else self.name


@attr.s(auto_attribs=True)
class FeatmonSpec:
    """Represents a Nimbus feature monitoring config file for a single application.

    The expected use is like::

        FeatmonSpec.from_file(Path("featmon/firefox_desktop.toml"))

    Config files are TOML and live in ``featmon/`` in metric-hub, one per
    application (e.g. ``firefox_desktop.toml``).  The ``dataset`` is inferred
    from the filename stem so it does not need to be repeated in the file.

    To load all configs from a metric-hub repo checkout::

        specs = FeatmonSpec.configs_from_repo(Path("/path/to/metric-hub"))
        for app_name, spec in specs:
            ...
    """

    dataset: str
    data_sources: dict[str, SourceTableSpec] = attr.Factory(dict)
    features: dict[str, FeatureSpec] = attr.Factory(dict)

    def __attrs_post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Validate data source types."""
        for name, source in self.data_sources.items():
            if source.type not in VALID_SOURCE_TYPES:
                raise ValueError(
                    f"data_source '{name}' has invalid type '{source.type}'. "
                    f"Must be one of: {sorted(VALID_SOURCE_TYPES)}"
                )

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], dataset: str) -> "FeatmonSpec":
        """Create a spec from an already-parsed dict (e.g. from ``toml.load()``)."""
        data_sources = {
            name: SourceTableSpec(name=name, **cfg)
            for name, cfg in d.get("data_sources", {}).items()
        }
        features = {
            name: FeatureSpec(
                name=name,
                slug=cfg.get("slug"),
                metrics_by_source=cfg.get("metrics_by_source", {}),
            )
            for name, cfg in d.get("features", {}).items()
        }
        return cls(dataset=dataset, data_sources=data_sources, features=features)

    @classmethod
    def from_file(cls, path: Path) -> "FeatmonSpec":
        """Create a spec by reading and parsing a TOML file.

        The dataset is inferred from the file stem (e.g. ``firefox_desktop.toml``
        → dataset ``firefox_desktop``).
        """
        return cls.from_dict(toml.load(str(path)), dataset=path.stem)

    @staticmethod
    def configs_from_repo(repo_path: Path) -> "list[tuple[str, FeatmonSpec]]":
        """Load all featmon configs from a metric-hub checkout.

        Args:
            repo_path: Path to the root of a metric-hub repository checkout.

        Returns:
            Sorted list of ``(app_name, spec)`` tuples, one per TOML file found
            in the ``featmon/`` directory.
        """
        config_dir = repo_path / FEATMON_DIR
        if not config_dir.is_dir():
            return []
        return [(p.stem, FeatmonSpec.from_file(p)) for p in sorted(config_dir.glob("*.toml"))]
