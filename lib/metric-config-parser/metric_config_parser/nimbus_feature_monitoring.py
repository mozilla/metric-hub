"""Spec for Nimbus feature monitoring TOML configs.

Config files live in the ``nimbus_feature_monitoring/`` directory of a metric-hub
repository checkout, with one TOML file per application (e.g. ``firefox_desktop.toml``).

Each file defines:
- ``dataset``: the BigQuery dataset name for the application
- ``source_tables``: BigQuery tables to query, each with a ``type`` of
  ``"metrics"``, ``"event_stream"``, or ``"clients_daily"``
- ``features``: Nimbus features and the metrics to collect per source table
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import attr
import toml



VALID_SOURCE_TYPES = frozenset({"metrics", "event_stream", "clients_daily"})

NIMBUS_FEATURE_MONITORING_DIR = "nimbus_feature_monitoring"


@attr.s(auto_attribs=True)
class NimbusFeatureMonitoringSpec:
    """Represents a Nimbus feature monitoring config file for a single application.

    The expected use is like::

        NimbusFeatureMonitoringSpec.from_dict(toml.load(my_config_file))

    Config files are TOML and live in ``nimbus_feature_monitoring/`` in metric-hub,
    one per application (e.g. ``firefox_desktop.toml``).

    To load all configs from a metric-hub repo checkout::

        specs = NimbusFeatureMonitoringSpec.configs_from_repo(Path("/path/to/metric-hub"))
        for app_name, spec in specs:
            ...
    """

    dataset: str
    source_tables: dict[str, Any] = attr.Factory(dict)
    features: dict[str, Any] = attr.Factory(dict)

    def __attrs_post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Validate source table types."""
        for name, table in self.source_tables.items():
            table_type = table.get("type", "metrics")
            if table_type not in VALID_SOURCE_TYPES:
                raise ValueError(
                    f"source_table '{name}' has invalid type '{table_type}'. "
                    f"Must be one of: {sorted(VALID_SOURCE_TYPES)}"
                )

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "NimbusFeatureMonitoringSpec":
        """Create a spec from an already-parsed dict (e.g. from ``toml.load()``)."""
        return cls(
            dataset=d["dataset"],
            source_tables=d.get("source_tables", {}),
            features=d.get("features", {}),
        )

    @classmethod
    def from_file(cls, path: Path) -> "NimbusFeatureMonitoringSpec":
        """Create a spec by reading and parsing a TOML file."""
        return cls.from_dict(toml.load(str(path)))

    @staticmethod
    def configs_from_repo(
        repo_path: Path,
    ) -> "list[tuple[str, NimbusFeatureMonitoringSpec]]":
        """Load all Nimbus feature monitoring configs from a metric-hub checkout.

        Args:
            repo_path: Path to the root of a metric-hub repository checkout.

        Returns:
            Sorted list of ``(app_name, spec)`` tuples, one per TOML file found
            in the ``nimbus_feature_monitoring/`` directory.
        """
        config_dir = repo_path / NIMBUS_FEATURE_MONITORING_DIR
        if not config_dir.is_dir():
            return []
        return [
            (p.stem, NimbusFeatureMonitoringSpec.from_file(p))
            for p in sorted(config_dir.glob("*.toml"))
        ]
