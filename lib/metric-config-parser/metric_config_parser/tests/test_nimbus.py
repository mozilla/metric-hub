import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
import toml
from cattrs.errors import ClassValidationError
from git import Repo

from metric_config_parser.aggregation import (
    Aggregation,
    Clause,
    Operator,
    RecencyEncoding,
    Threshold,
)
from metric_config_parser.aggregation_plan import aggregation_plan
from metric_config_parser.analysis import AnalysisSpec
from metric_config_parser.config import (
    NIMBUS_DEFINITIONS_DIR,
    ConfigCollection,
    DefinitionConfig,
    LocalConfigCollection,
    NimbusConfig,
    Outcome,
    entity_from_path,
    is_nimbus_definition,
)
from metric_config_parser.data_source import DataSourceReference
from metric_config_parser.definition import DefinitionSpec
from metric_config_parser.function import FunctionsSpec
from metric_config_parser.metric import MetricDefinition, MetricReference
from metric_config_parser.nimbus import (
    NIMBUS_DIR,
    NIMBUS_METRIC_KEYS,
    NimbusConfigKind,
    NimbusDefinitionMismatch,
    NimbusSpec,
)
from metric_config_parser.outcome import OutcomeSpec
from metric_config_parser.util import converter, normalize_sql

TEST_DIR = Path(__file__).parent
FIXTURE_DIR = TEST_DIR / "data" / "nimbus_repo"
DEFINITIONS_FILE = FIXTURE_DIR / "definitions" / "firefox_desktop.toml"
NIMBUS_FILE = FIXTURE_DIR / NIMBUS_DEFINITIONS_DIR / "firefox_desktop.toml"
EXAMPLE_FILE = TEST_DIR.parents[3] / NIMBUS_DEFINITIONS_DIR / "example_config.toml.example"
FUNCTIONS_FILE = TEST_DIR / "data" / "definitions" / "functions.toml"
ACTIVE_HOURS_DEFINITION = """[metrics.active_hours]
select_expression = '{{agg_sum("active_hours_sum")}}'
data_source = "clients_daily"
"""


def make_repo(tmp_path, source=FIXTURE_DIR):
    shutil.copytree(source, tmp_path, dirs_exist_ok=True)
    return init_repo(tmp_path)


def init_repo(tmp_path):
    r = Repo.init(tmp_path)
    r.config_writer().set_value("user", "name", "test").release()
    r.config_writer().set_value("user", "email", "test@example.com").release()
    r.config_writer().set_value("commit", "gpgsign", "false").release()
    r.git.add(".")
    r.git.commit("-m", "commit")
    return tmp_path


def make_definitions_repo(root, definitions_toml):
    definitions_dir = root / "definitions"
    definitions_dir.mkdir(parents=True)
    (definitions_dir / "firefox_desktop.toml").write_text(definitions_toml)
    return init_repo(root)


def write_nimbus(root, metrics_toml):
    nimbus_dir = root / NIMBUS_DEFINITIONS_DIR
    nimbus_dir.mkdir(parents=True, exist_ok=True)
    (nimbus_dir / "firefox_desktop.toml").write_text(metrics_toml)


def write_fenix_nimbus(root, metrics_toml):
    (root / "definitions" / "fenix.toml").write_text(
        '[data_sources.clients_daily]\nfrom_expression = "mozdata.telemetry.clients_daily"\n'
    )
    nimbus_dir = root / NIMBUS_DEFINITIONS_DIR
    nimbus_dir.mkdir(parents=True, exist_ok=True)
    (nimbus_dir / "fenix.toml").write_text(metrics_toml)


def write_nimbus_defaults_file(root, app_name, metrics_toml):
    defaults_dir = root / NIMBUS_DIR / "defaults"
    defaults_dir.mkdir(parents=True, exist_ok=True)
    (defaults_dir / f"{app_name}.toml").write_text(metrics_toml)


def write_nimbus_outcome_file(root, app_name, outcome_name, metrics_toml):
    outcome_dir = root / NIMBUS_DIR / "outcomes" / app_name
    outcome_dir.mkdir(parents=True, exist_ok=True)
    (outcome_dir / f"{outcome_name}.toml").write_text(metrics_toml)


def collection_with_functions(path):
    collection = LocalConfigCollection.from_local_path(path)
    collection.functions = FunctionsSpec.from_dict(toml.load(FUNCTIONS_FILE))
    return collection


def replace_active_hours_definition(root, definition_toml):
    definitions_file = root / "definitions" / "firefox_desktop.toml"
    definitions_file.write_text(
        definitions_file.read_text().replace(ACTIVE_HOURS_DEFINITION, definition_toml)
    )


def parse_metric(**fields):
    return converter.structure(
        {"name": "m", "data_source": "clients_daily", **fields}, MetricDefinition
    )


def parse_nimbus(**fields):
    return NimbusSpec.from_dict({"metrics": {"m": fields}}, "firefox_desktop")


class TestAggregationFields:
    def test_nimbus_file(self):
        spec = NimbusSpec.from_file(NIMBUS_FILE)

        assert set(spec.metrics) == {
            "days_of_use",
            "qualified_cumulative_days_of_use",
            "active_hours",
            "is_default_browser",
            "retained",
            "active_in_last_3_days_legacy",
            "daily_active_users_per_1000_clients_legacy",
        }

    def test_sum(self):
        metric = NimbusSpec.from_file(NIMBUS_FILE).metrics["active_hours"]

        assert metric.name == "active_hours"
        assert metric.data_source == DataSourceReference(name="clients_daily")
        assert metric.select_expression is None
        assert metric.aggregation == Aggregation.SUM
        assert metric.column == "active_hours_sum"
        assert metric.cumulative_window == 7
        assert metric.incremental_window is None
        assert metric.repeat_windows is True
        assert metric.statistics == {"bootstrap_mean": {}}
        assert metric.friendly_name == "Active hours"
        assert metric.description == "Time during which Firefox received user input."
        assert metric.bigger_is_better is True

    def test_sum_with_threshold(self):
        metric = NimbusSpec.from_file(NIMBUS_FILE).metrics["retained"]

        assert metric.aggregation == Aggregation.SUM
        assert metric.column == "pings_aggregated_by_this_row"
        assert metric.threshold == Threshold(op=Operator.GT, value=0)
        assert metric.cumulative_window is None
        assert metric.incremental_window == 7
        assert metric.repeat_windows is True

    def test_count_where_with_clauses(self):
        metric = NimbusSpec.from_file(NIMBUS_FILE).metrics["qualified_cumulative_days_of_use"]

        assert metric.aggregation == Aggregation.COUNT_WHERE
        assert metric.column is None
        assert metric.where == [
            Clause(column="active_hours_sum", op=Operator.GT, value=0),
            Clause(
                column="scalar_parent_browser_engagement_total_uri_count_normal_and_private_mode_sum",
                op=Operator.GT,
                value=0,
            ),
        ]
        assert metric.conditions == metric.where

    def test_any_with_column_shorthand(self):
        metric = NimbusSpec.from_file(NIMBUS_FILE).metrics["is_default_browser"]

        assert metric.aggregation == Aggregation.ANY
        assert metric.column == "is_default_browser"
        assert metric.where == []
        assert metric.conditions == [Clause(column="is_default_browser")]

    def test_recency_within(self):
        metric = NimbusSpec.from_file(NIMBUS_FILE).metrics["active_in_last_3_days_legacy"]

        assert metric.aggregation == Aggregation.RECENCY_WITHIN
        assert metric.column == "days_active_bits"
        assert metric.within_days == 3

    def test_count_where_with_scale(self):
        metric = NimbusSpec.from_file(NIMBUS_FILE).metrics[
            "daily_active_users_per_1000_clients_legacy"
        ]

        assert metric.aggregation == Aggregation.COUNT_WHERE
        assert metric.conditions == [Clause(column="is_dau")]
        assert metric.scale == 1000

    def test_count(self):
        metric = NimbusSpec.from_file(NIMBUS_FILE).metrics["days_of_use"]

        assert metric.aggregation == Aggregation.COUNT
        assert metric.column == "submission_date"

    def test_one_off_window(self):
        metric = parse_metric(aggregation="sum", column="a", cumulative_window=3)

        assert metric.cumulative_window == 3
        assert metric.incremental_window is None
        assert metric.repeat_windows is False

    def test_both_window_families(self):
        metric = parse_metric(
            aggregation="sum",
            column="a",
            cumulative_window=7,
            incremental_window=7,
            repeat_windows=True,
        )

        assert metric.cumulative_window == 7
        assert metric.incremental_window == 7
        assert metric.repeat_windows is True

    def test_no_windows(self):
        metric = parse_metric(aggregation="sum", column="a")

        assert metric.cumulative_window is None
        assert metric.incremental_window is None
        assert metric.repeat_windows is False

    def test_null_operators_take_no_value(self):
        metric = parse_metric(
            aggregation="count_where",
            where=[{"column": "a", "op": "IS NULL"}, {"column": "b", "op": "IS NOT NULL"}],
        )

        assert metric.where == [
            Clause(column="a", op=Operator.IS_NULL),
            Clause(column="b", op=Operator.IS_NOT_NULL),
        ]

    def test_select_expression_metric_has_no_aggregation_fields(self):
        metric = parse_metric(select_expression="SUM(a)")

        assert metric.aggregation is None
        assert metric.column is None
        assert metric.where == []
        assert metric.conditions == []
        assert metric.repeat_windows is False

    def test_direct_construction_validates(self):
        with pytest.raises(ValueError, match="requires a column"):
            MetricDefinition(name="m", aggregation=Aggregation.SUM)


class TestAtMostOneDefinition:
    def test_rejects_select_expression_and_aggregation(self):
        with pytest.raises(ClassValidationError) as exc_info:
            parse_metric(select_expression="SUM(a)", aggregation="sum", column="a")

        assert exc_info.group_contains(
            ValueError, match="declare either select_expression or aggregation, not both"
        )

    def test_rejects_both_in_definitions(self):
        with pytest.raises(ClassValidationError) as exc_info:
            DefinitionSpec.from_dict(
                {
                    "metrics": {
                        "m": {
                            "select_expression": "SUM(a)",
                            "data_source": "clients_daily",
                            "aggregation": "sum",
                            "column": "a",
                        }
                    }
                }
            )

        assert exc_info.group_contains(ValueError, match="not both", depth=None)

    def test_rejects_both_in_outcome(self):
        with pytest.raises(ClassValidationError) as exc_info:
            OutcomeSpec.from_dict(
                {
                    "friendly_name": "Outcome",
                    "description": "Outcome",
                    "metrics": {
                        "m": {
                            "select_expression": "SUM(a)",
                            "data_source": "clients_daily",
                            "aggregation": "sum",
                            "column": "a",
                        }
                    },
                }
            )

        assert exc_info.group_contains(ValueError, match="not both")

    def test_accepts_neither_in_definitions(self):
        spec = DefinitionSpec.from_dict(
            {"metrics": {"m": {"data_source": "clients_daily", "friendly_name": "M"}}}
        )

        metric = spec.metrics.definitions["m"]
        assert metric.select_expression is None
        assert metric.aggregation is None

    def test_accepts_aggregation_in_definitions(self):
        spec = DefinitionSpec.from_dict(
            {
                "metrics": {
                    "m": {"data_source": "clients_daily", "aggregation": "sum", "column": "a"}
                }
            }
        )

        assert spec.metrics.definitions["m"].aggregation == Aggregation.SUM

    def test_statistics_only_override(self):
        spec = AnalysisSpec.from_dict(
            {
                "metrics": {
                    "weekly": ["active_hours"],
                    "active_hours": {"statistics": {"bootstrap_mean": {}}},
                }
            }
        )

        metric = spec.metrics.definitions["active_hours"]
        assert metric.statistics == {"bootstrap_mean": {}}
        assert metric.select_expression is None
        assert metric.aggregation is None

    def test_depends_on_metric(self):
        spec = AnalysisSpec.from_dict(
            {
                "metrics": {
                    "ratio": {
                        "depends_on": ["active_hours", "uri_count"],
                        "statistics": {"population_ratio": {}},
                    }
                }
            }
        )

        assert spec.metrics.definitions["ratio"].depends_on == [
            MetricReference("active_hours"),
            MetricReference("uri_count"),
        ]

    def test_loads_neither_from_local_path(self, tmp_path):
        shutil.copytree(FIXTURE_DIR / "definitions", tmp_path / "definitions")
        definitions = toml.load(DEFINITIONS_FILE)
        definitions["metrics"]["uri_count_override"] = {"statistics": {"bootstrap_mean": {}}}
        (tmp_path / "definitions" / "firefox_desktop.toml").write_text(toml.dumps(definitions))

        collection = LocalConfigCollection.from_local_path(tmp_path)

        metric = collection.get_metric_definition("uri_count_override", "firefox_desktop")
        assert metric is not None
        assert metric.statistics == {"bootstrap_mean": {}}


class TestAggregationFieldRejections:
    @pytest.mark.parametrize(
        ("fields", "match"),
        [
            ({"aggregation": "count_distinct", "column": "a"}, "is not one of"),
            ({"aggregation": "average", "column": "a"}, "is not one of"),
            ({"column": "a"}, "require aggregation"),
            ({"where": [{"column": "a"}]}, "require aggregation"),
            ({"within_days": 3}, "require aggregation"),
            ({"threshold": {"op": ">", "value": 0}}, "require aggregation"),
            ({"scale": 1000}, "require aggregation"),
            ({"encoding": "days"}, "require aggregation"),
            ({"cumulative_window": 7}, "require aggregation"),
            ({"incremental_window": 7}, "require aggregation"),
            ({"repeat_windows": True}, "require aggregation"),
            ({"select_expression": "SUM(a)", "column": "a"}, "require aggregation"),
            ({"aggregation": "sum"}, "requires a column"),
            ({"aggregation": "count"}, "requires a column"),
            ({"aggregation": "recency_within", "within_days": 3}, "requires a column"),
            (
                {"aggregation": "sum", "column": "a", "where": [{"column": "b"}]},
                "does not take where",
            ),
            (
                {"aggregation": "count", "column": "a", "where": [{"column": "b"}]},
                "does not take where",
            ),
            (
                {
                    "aggregation": "recency_within",
                    "column": "a",
                    "within_days": 3,
                    "where": [{"column": "b"}],
                },
                "does not take where",
            ),
            ({"aggregation": "count_where"}, "exactly one of column or where"),
            ({"aggregation": "any"}, "exactly one of column or where"),
            (
                {"aggregation": "count_where", "column": "a", "where": [{"column": "b"}]},
                "exactly one of column or where",
            ),
            (
                {"aggregation": "any", "column": "a", "where": [{"column": "b"}]},
                "exactly one of column or where",
            ),
            (
                {"aggregation": "recency_within", "column": "a"},
                "within_days must be a positive integer",
            ),
            (
                {"aggregation": "recency_within", "column": "a", "within_days": 0},
                "within_days must be a positive integer",
            ),
            (
                {"aggregation": "recency_within", "column": "a", "within_days": -1},
                "within_days must be a positive integer",
            ),
            (
                {"aggregation": "recency_within", "column": "a", "within_days": 2.5},
                "within_days must be a positive integer",
            ),
            (
                {"aggregation": "recency_within", "column": "a", "within_days": True},
                "within_days must be a positive integer",
            ),
            (
                {"aggregation": "recency_within", "column": "a", "within_days": 29},
                "within_days must be at most 28",
            ),
            (
                {
                    "aggregation": "recency_within",
                    "column": "a",
                    "encoding": "days",
                    "within_days": 29,
                },
                "within_days must be at most 28",
            ),
            (
                {"aggregation": "sum", "column": "a", "within_days": 3},
                "only valid for recency_within",
            ),
            (
                {"aggregation": "any", "column": "a", "within_days": 3},
                "only valid for recency_within",
            ),
            ({"aggregation": "sum", "column": "COALESCE(a, 0)"}, "must be a plain column name"),
            ({"aggregation": "sum", "column": "1a"}, "must be a plain column name"),
            ({"aggregation": "sum", "column": "a.b"}, "must be a plain column name"),
            ({"aggregation": "sum", "column": 1}, "must be a plain column name"),
            (
                {"aggregation": "count_where", "where": [{"column": "a > 0"}]},
                "must be a plain column name",
            ),
            (
                {"aggregation": "count_where", "where": [{"op": ">", "value": 0}]},
                "requires a column",
            ),
            (
                {
                    "aggregation": "count_where",
                    "where": [{"column": "a", "op": "LIKE", "value": 0}],
                },
                "is not one of",
            ),
            (
                {"aggregation": "count_where", "where": [{"column": "a", "op": ">"}]},
                "requires a value",
            ),
            (
                {
                    "aggregation": "count_where",
                    "where": [{"column": "a", "op": "IS NULL", "value": 0}],
                },
                "takes no value",
            ),
            (
                {"aggregation": "count_where", "where": [{"column": "a", "value": 0}]},
                "takes no value",
            ),
            (
                {"aggregation": "count_where", "where": [{"column": "a", "or": "b"}]},
                "unexpected keys",
            ),
            (
                {"aggregation": "sum", "column": "a", "threshold": {"op": "IS NULL", "value": 0}},
                "must be a comparison",
            ),
            (
                {"aggregation": "sum", "column": "a", "threshold": {"op": "~", "value": 0}},
                "is not one of",
            ),
            (
                {"aggregation": "sum", "column": "a", "threshold": {"op": ">", "value": "0"}},
                "must be a number",
            ),
            (
                {"aggregation": "sum", "column": "a", "threshold": {"op": ">"}},
                "requires op and value",
            ),
            (
                {"aggregation": "sum", "column": "a", "threshold": {"op": ">", "value": 0, "x": 1}},
                "unexpected keys",
            ),
            ({"aggregation": "sum", "column": "a", "scale": "1000"}, "scale must be a number"),
            ({"aggregation": "sum", "column": "a", "scale": True}, "scale must be a number"),
            (
                {"aggregation": "sum", "column": "a", "cumulative_window": 0},
                "cumulative_window must be a positive integer",
            ),
            (
                {"aggregation": "sum", "column": "a", "cumulative_window": -7},
                "cumulative_window must be a positive integer",
            ),
            (
                {"aggregation": "sum", "column": "a", "cumulative_window": 7.0},
                "cumulative_window must be a positive integer",
            ),
            (
                {"aggregation": "sum", "column": "a", "cumulative_window": True},
                "cumulative_window must be a positive integer",
            ),
            (
                {"aggregation": "sum", "column": "a", "incremental_window": 0},
                "incremental_window must be a positive integer",
            ),
            (
                {"aggregation": "sum", "column": "a", "incremental_window": -7},
                "incremental_window must be a positive integer",
            ),
            (
                {"aggregation": "sum", "column": "a", "incremental_window": 7.0},
                "incremental_window must be a positive integer",
            ),
            (
                {"aggregation": "sum", "column": "a", "incremental_window": True},
                "incremental_window must be a positive integer",
            ),
            (
                {"aggregation": "sum", "column": "a", "repeat_windows": True},
                "repeat_windows requires cumulative_window or incremental_window",
            ),
            (
                {"aggregation": "sum", "column": "a", "cumulative_window": 7, "repeat_windows": 1},
                "repeat_windows must be a boolean",
            ),
            (
                {"aggregation": "sum", "column": "a", "encoding": "days"},
                "encoding is only valid for recency_within",
            ),
            (
                {"aggregation": "any", "column": "a", "encoding": "days"},
                "encoding is only valid for recency_within",
            ),
            (
                {"aggregation": "recency_within", "column": "a", "within_days": 3, "encoding": "x"},
                "is not one of",
            ),
        ],
    )
    def test_rejects(self, fields, match):
        with pytest.raises(ClassValidationError) as exc_info:
            parse_metric(**fields)

        assert exc_info.group_contains(ValueError, match=match)


class TestNimbusSpec:
    @pytest.mark.parametrize(
        ("fields", "match"),
        [
            (
                {"aggregation": "sum", "column": "a", "select_expression": "SUM(a)"},
                r"select_expression is not allowed\. Use aggregation instead\.",
            ),
            (
                {"select_expression": "SUM(a)"},
                r"select_expression is not allowed\. Use aggregation instead\.",
            ),
            ({"column": "a"}, "aggregation is required"),
            ({"statistics": {"bootstrap_mean": {}}}, "aggregation is required"),
            (
                {"aggregation": "sum", "column": "a", "windows": ["cumulative_weekly"]},
                "unexpected keys",
            ),
            ({"aggregation": "sum", "column": "a", "disjoint_window": 7}, "unexpected keys"),
            (
                {"aggregation": "sum", "column": "a", "analysis_bases": ["exposures"]},
                "unexpected keys",
            ),
            ({"aggregation": "sum", "column": "a", "type": "scalar"}, "unexpected keys"),
            ({"aggregation": "sum", "column": "a", "depends_on": ["b"]}, "unexpected keys"),
            ({"aggregation": "sum", "column": "a", "Column": "b"}, "unexpected keys"),
        ],
    )
    def test_rejects(self, fields, match):
        with pytest.raises(ValueError, match=match):
            parse_nimbus(data_source="clients_daily", **fields)

    def test_rejects_missing_data_source(self):
        with pytest.raises(ValueError, match="data_source is required"):
            parse_nimbus(aggregation="sum", column="a")

    def test_rejects_unknown_top_level_key(self):
        with pytest.raises(ValueError, match="data_sources"):
            NimbusSpec.from_dict({"metrics": {}, "data_sources": {}}, "firefox_desktop")

    def test_applies_aggregation_rules(self):
        with pytest.raises(ClassValidationError) as exc_info:
            parse_nimbus(data_source="clients_daily", aggregation="sum")

        assert exc_info.group_contains(ValueError, match="requires a column")

    def test_accepts_encoding(self):
        spec = parse_nimbus(
            data_source="clients_daily",
            aggregation="recency_within",
            column="a",
            within_days=3,
            encoding="days",
        )

        assert spec.metrics["m"].encoding == RecencyEncoding.DAYS

    def test_invalid_file_fails_to_load(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus(
            tmp_path,
            '[metrics.bad]\ndata_source = "clients_daily"\nselect_expression = "SUM(a)"\n',
        )

        with pytest.raises(
            ValueError, match=r"select_expression is not allowed\. Use aggregation instead\."
        ):
            NimbusSpec.from_file(tmp_path / NIMBUS_DEFINITIONS_DIR / "firefox_desktop.toml")

    def test_invalid_file_is_skipped_by_collection(self, tmp_path, caplog):
        make_repo(tmp_path)
        write_nimbus(
            tmp_path,
            '[metrics.bad]\ndata_source = "clients_daily"\nselect_expression = "SUM(a)"\n',
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)

        assert collection.nimbus_configs == []
        assert collection.get_metric_definition("uri_count", "firefox_desktop") is not None
        assert any(
            "select_expression is not allowed" in record.message for record in caplog.records
        )


class TestNimbusCollection:
    def test_loads_from_local_repo(self, tmp_path):
        collection = ConfigCollection.from_github_repo(make_repo(tmp_path))

        assert len(collection.definitions) == 1
        assert len(collection.nimbus_configs) == 1
        config = collection.nimbus_configs[0]
        assert config.slug == "firefox_desktop"
        assert config.spec == NimbusSpec.from_file(NIMBUS_FILE)

    def test_loads_from_local_path(self):
        collection = LocalConfigCollection.from_local_path(FIXTURE_DIR)

        assert [config.slug for config in collection.nimbus_configs] == ["firefox_desktop"]
        assert "active_hours" in collection.nimbus_configs[0].spec.metrics

    def test_get_nimbus_metric_definition(self):
        collection = LocalConfigCollection.from_local_path(FIXTURE_DIR)

        metric = collection.get_nimbus_metric_definition("active_hours", "firefox_desktop")
        assert metric == NimbusSpec.from_file(NIMBUS_FILE).metrics["active_hours"]
        assert collection.get_nimbus_metric_definition("uri_count", "firefox_desktop") is None
        assert collection.get_nimbus_metric_definition("active_hours", "fenix") is None

    def test_get_metric_definition_reads_definitions_only(self):
        collection = LocalConfigCollection.from_local_path(FIXTURE_DIR)

        assert collection.get_metric_definition("days_of_use", "firefox_desktop") is None
        assert collection.get_metric_definition("uri_count", "firefox_desktop") is not None

    def test_no_nimbus_directory(self, config_collection):
        assert config_collection.nimbus_configs == []

    def test_entity_from_path(self):
        entity = entity_from_path(NIMBUS_FILE)

        assert isinstance(entity, NimbusConfig)
        assert entity.slug == "firefox_desktop"
        assert entity.spec == NimbusSpec.from_file(NIMBUS_FILE)

    def test_entity_from_path_definitions(self):
        assert isinstance(entity_from_path(DEFINITIONS_FILE), DefinitionConfig)

    def test_is_nimbus_definition(self):
        assert is_nimbus_definition(NIMBUS_FILE)
        assert not is_nimbus_definition(DEFINITIONS_FILE)
        assert not is_nimbus_definition(Path("jetstream") / "definitions" / "firefox_desktop.toml")

    def test_entity_validates_against_collection(self):
        collection = LocalConfigCollection.from_local_path(FIXTURE_DIR)

        entity_from_path(NIMBUS_FILE).validate(collection)

    def test_merge_same_file_adds_new_metric_keeps_existing(self, tmp_path):
        base = make_repo(tmp_path / "base")
        override = make_repo(tmp_path / "override")
        write_nimbus(
            override,
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        Repo(override).git.commit("-am", "add a metric to nimbus")

        collection = ConfigCollection.from_github_repo(base)
        base_metrics = set(collection.nimbus_configs[0].spec.metrics)
        collection.merge(ConfigCollection.from_github_repo(override))

        assert len(collection.nimbus_configs) == 1
        assert set(collection.nimbus_configs[0].spec.metrics) == base_metrics | {"search_count"}

    def test_merge_same_file_redefines_one_metric_keeps_others(self, tmp_path):
        base = make_repo(tmp_path / "base")
        override = make_repo(tmp_path / "override")
        write_nimbus(
            override,
            '[metrics.active_hours]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "active_hours_sum_v2"\n',
        )
        Repo(override).git.commit("-am", "redefine a nimbus metric")

        collection = ConfigCollection.from_github_repo(base)
        base_metrics = set(collection.nimbus_configs[0].spec.metrics)
        collection.merge(ConfigCollection.from_github_repo(override))

        assert len(collection.nimbus_configs) == 1
        merged_metrics = collection.nimbus_configs[0].spec.metrics
        assert set(merged_metrics) == base_metrics
        assert merged_metrics["active_hours"].column == "active_hours_sum_v2"

    def test_merge_keeps_configs_for_other_apps(self, tmp_path):
        collection = ConfigCollection.from_github_repo(make_repo(tmp_path))
        other = ConfigCollection(
            nimbus_configs=[NimbusConfig(slug="fenix", app_name="fenix", spec=NimbusSpec())]
        )

        collection.merge(other)

        assert sorted(config.slug for config in collection.nimbus_configs) == [
            "fenix",
            "firefox_desktop",
        ]

    def test_merge_overrides_one_metric_keeps_others_in_same_file(self, tmp_path):
        base = make_repo(tmp_path / "base")
        override_root = tmp_path / "override"
        (override_root / "definitions").mkdir(parents=True)
        (override_root / "definitions" / "firefox_desktop.toml").write_text(
            '[data_sources.clients_daily]\nfrom_expression = "mozdata.telemetry.clients_daily"\n'
        )
        write_nimbus_defaults_file(
            override_root,
            "firefox_desktop",
            '[metrics.active_hours]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "active_hours_sum"\n',
        )
        init_repo(override_root)

        collection = ConfigCollection.from_github_repo(base)
        collection.merge(ConfigCollection.from_github_repo(override_root))

        definitions_config = next(
            c for c in collection.nimbus_configs if c.kind == NimbusConfigKind.DEFINITIONS
        )
        assert "active_hours" not in definitions_config.spec.metrics
        assert "days_of_use" in definitions_config.spec.metrics
        assert "is_default_browser" in definitions_config.spec.metrics

        defaults_config = next(
            c for c in collection.nimbus_configs if c.kind == NimbusConfigKind.DEFAULTS
        )
        assert set(defaults_config.spec.metrics) == {"active_hours"}

    def test_merge_adds_new_file_without_dropping_unrelated_metrics(self, tmp_path):
        base = make_repo(tmp_path / "base")
        override_root = make_repo(tmp_path / "override")
        write_nimbus_outcome_file(
            override_root,
            "firefox_desktop",
            "engagement",
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        Repo(override_root).git.add(".")
        Repo(override_root).git.commit("-am", "add a new outcome file")

        collection = ConfigCollection.from_github_repo(base)
        collection.merge(ConfigCollection.from_github_repo(override_root))

        definitions_config = next(
            c for c in collection.nimbus_configs if c.kind == NimbusConfigKind.DEFINITIONS
        )
        assert "active_hours" in definitions_config.spec.metrics
        assert "days_of_use" in definitions_config.spec.metrics

        outcome_config = next(
            c for c in collection.nimbus_configs if c.kind == NimbusConfigKind.OUTCOMES
        )
        assert set(outcome_config.spec.metrics) == {"search_count"}

    def test_double_merge_is_idempotent(self, tmp_path):
        base = make_repo(tmp_path / "base")
        override_root = tmp_path / "override"
        (override_root / "definitions").mkdir(parents=True)
        (override_root / "definitions" / "firefox_desktop.toml").write_text(
            '[data_sources.clients_daily]\nfrom_expression = "mozdata.telemetry.clients_daily"\n'
        )
        write_nimbus_defaults_file(
            override_root,
            "firefox_desktop",
            '[metrics.active_hours]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "active_hours_sum"\n',
        )
        init_repo(override_root)

        collection = ConfigCollection.from_github_repo(base)
        collection.merge(ConfigCollection.from_github_repo(override_root))
        once = {
            (c.app_name, c.kind, c.slug): dict(c.spec.metrics) for c in collection.nimbus_configs
        }

        collection.merge(ConfigCollection.from_github_repo(override_root))
        twice = {
            (c.app_name, c.kind, c.slug): dict(c.spec.metrics) for c in collection.nimbus_configs
        }

        assert once == twice

    def test_merge_overriding_one_app_leaves_another_apps_same_name_metric(self, tmp_path):
        base = tmp_path / "base"
        make_repo(base)
        write_fenix_nimbus(
            base,
            '[metrics.active_hours]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "active_hours_sum"\n',
        )
        Repo(base).git.add(".")
        Repo(base).git.commit("-am", "add fenix active_hours")

        override_root = tmp_path / "override"
        (override_root / "definitions").mkdir(parents=True)
        (override_root / "definitions" / "firefox_desktop.toml").write_text(
            '[data_sources.clients_daily]\nfrom_expression = "mozdata.telemetry.clients_daily"\n'
        )
        write_nimbus_defaults_file(
            override_root,
            "firefox_desktop",
            '[metrics.active_hours]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "active_hours_sum"\n',
        )
        init_repo(override_root)

        collection = ConfigCollection.from_github_repo(base)
        collection.merge(ConfigCollection.from_github_repo(override_root))

        firefox_desktop_definitions = next(
            c
            for c in collection.nimbus_configs
            if c.app_name == "firefox_desktop" and c.kind == NimbusConfigKind.DEFINITIONS
        )
        assert "active_hours" not in firefox_desktop_definitions.spec.metrics

        fenix_definitions = next(
            c
            for c in collection.nimbus_configs
            if c.app_name == "fenix" and c.kind == NimbusConfigKind.DEFINITIONS
        )
        assert "active_hours" in fenix_definitions.spec.metrics

    def test_config_failing_validation_is_dropped_at_load(self, tmp_path, caplog):
        make_repo(tmp_path)
        write_nimbus(
            tmp_path,
            '[metrics.search_count]\ndata_source = "search_clients_engines_sources_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n'
            '[metrics.active_hours]\nfriendly_name = "Active hours"\n'
            'data_source = "clients_daily"\naggregation = "sum"\ncolumn = "active_hours_sum"\n',
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)

        assert collection.nimbus_configs == []
        assert collection.get_metric_definition("uri_count", "firefox_desktop") is not None
        assert any(
            "search_clients_engines_sources_daily" in record.message for record in caplog.records
        )

    def test_config_from_another_app_is_dropped_at_load(self, tmp_path, caplog):
        make_repo(tmp_path)
        nimbus_dir = tmp_path / NIMBUS_DEFINITIONS_DIR
        (nimbus_dir / "firefox_desktop.toml").rename(nimbus_dir / "fenix.toml")

        collection = LocalConfigCollection.from_local_path(tmp_path)

        assert collection.nimbus_configs == []
        assert any(
            "not defined in definitions/fenix.toml" in record.message for record in caplog.records
        )

    def test_entity_from_path_raises_on_invalid_metric(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus(
            tmp_path,
            '[metrics.bad]\ndata_source = "clients_daily"\nselect_expression = "SUM(a)"\n',
        )

        with pytest.raises(ValueError, match=r"select_expression is not allowed"):
            entity_from_path(tmp_path / NIMBUS_DEFINITIONS_DIR / "firefox_desktop.toml")

    def test_validate_raises_on_undefined_data_source(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus(
            tmp_path,
            '[metrics.search_count]\ndata_source = "search_clients_engines_sources_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        entity = entity_from_path(tmp_path / NIMBUS_DEFINITIONS_DIR / "firefox_desktop.toml")
        collection = LocalConfigCollection.from_local_path(tmp_path)

        with pytest.raises(ValueError, match="search_clients_engines_sources_daily"):
            entity.validate(collection)

    def test_unknown_metric_key_skips_file_others_still_load(self, tmp_path, caplog):
        make_repo(tmp_path)
        write_fenix_nimbus(
            tmp_path,
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        write_nimbus(
            tmp_path,
            '[metrics.active_hours]\nfriendly_name = "Active hours"\n'
            'data_source = "clients_daily"\naggregation = "sum"\ncolumn = "active_hours_sum"\n'
            "bogus = 1\n",
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)

        assert {config.slug for config in collection.nimbus_configs} == {"fenix"}
        assert collection.get_metric_definition("uri_count", "firefox_desktop") is not None
        assert any("firefox_desktop.toml" in record.message for record in caplog.records)

    def test_unknown_top_level_table_skips_file_others_still_load(self, tmp_path, caplog):
        make_repo(tmp_path)
        write_fenix_nimbus(
            tmp_path,
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        write_nimbus(
            tmp_path,
            '[data_sources]\n[metrics.active_hours]\nfriendly_name = "Active hours"\n'
            'data_source = "clients_daily"\naggregation = "sum"\ncolumn = "active_hours_sum"\n',
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)

        assert {config.slug for config in collection.nimbus_configs} == {"fenix"}
        assert collection.get_metric_definition("uri_count", "firefox_desktop") is not None
        assert any("firefox_desktop.toml" in record.message for record in caplog.records)

    def test_unparseable_toml_skips_file_others_still_load(self, tmp_path, caplog):
        make_repo(tmp_path)
        write_fenix_nimbus(
            tmp_path,
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        write_nimbus(tmp_path, "[metrics.active_hours\n")

        collection = LocalConfigCollection.from_local_path(tmp_path)

        assert {config.slug for config in collection.nimbus_configs} == {"fenix"}
        assert collection.get_metric_definition("uri_count", "firefox_desktop") is not None
        assert any("firefox_desktop.toml" in record.message for record in caplog.records)

    def test_same_metric_in_definitions_and_nimbus(self, tmp_path):
        collection = ConfigCollection.from_github_repo(make_repo(tmp_path))

        definition = collection.get_metric_definition("active_hours", "firefox_desktop")
        nimbus_definition = collection.get_nimbus_metric_definition(
            "active_hours", "firefox_desktop"
        )
        assert definition is not None
        assert definition.select_expression == '{{agg_sum("active_hours_sum")}}'
        assert definition.aggregation is None
        assert nimbus_definition is not None
        assert nimbus_definition == NimbusSpec.from_file(NIMBUS_FILE).metrics["active_hours"]
        assert nimbus_definition.select_expression is None
        assert nimbus_definition.aggregation == Aggregation.SUM

    def test_resolves_data_source_from_another_repo(self, tmp_path):
        nimbus_repo = make_repo(tmp_path / "metric-hub")
        write_nimbus(
            nimbus_repo,
            '[metrics.search_count]\ndata_source = "search_clients"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        Repo(nimbus_repo).git.commit("-am", "use search_clients")
        data_source_repo = make_definitions_repo(
            tmp_path / "jetstream",
            '[data_sources.search_clients]\nfrom_expression = "mozdata.search.search_clients"\n',
        )

        collection = ConfigCollection.from_github_repo(nimbus_repo)
        assert collection.nimbus_configs == []

        collection = ConfigCollection.from_github_repos([str(nimbus_repo), str(data_source_repo)])
        assert set(collection.nimbus_configs[0].spec.metrics) == {"search_count"}

        collection = collection.as_of(datetime.now(UTC))
        assert set(collection.nimbus_configs[0].spec.metrics) == {"search_count"}

    def test_config_missing_data_source_from_every_repo_is_dropped(self, tmp_path, caplog):
        nimbus_repo = make_repo(tmp_path / "metric-hub")
        write_nimbus(
            nimbus_repo,
            '[metrics.search_count]\ndata_source = "search_clients"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        Repo(nimbus_repo).git.commit("-am", "use search_clients")
        other_repo = make_definitions_repo(
            tmp_path / "jetstream",
            '[data_sources.events]\nfrom_expression = "mozdata.firefox_desktop.events"\n',
        )

        collection = ConfigCollection.from_github_repos([str(nimbus_repo), str(other_repo)])

        assert collection.nimbus_configs == []
        assert any("'search_clients'" in record.message for record in caplog.records)

    def test_skips_validation_when_disabled(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus(
            tmp_path,
            '[metrics.search_count]\ndata_source = "search_clients"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        Repo(tmp_path).git.commit("-am", "use search_clients")

        collection = ConfigCollection.from_github_repo(tmp_path, validate_nimbus=False)

        assert set(collection.nimbus_configs[0].spec.metrics) == {"search_count"}

    def test_strict_raises_on_unknown_metric_key(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus(
            tmp_path,
            '[metrics.active_hours]\nfriendly_name = "Active hours"\n'
            'data_source = "clients_daily"\naggregation = "sum"\ncolumn = "active_hours_sum"\n'
            "bogus = 1\n",
        )

        with pytest.raises(ValueError, match="unexpected keys"):
            LocalConfigCollection.from_local_path(tmp_path, strict_nimbus=True)

    def test_strict_raises_on_unparseable_toml(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus(tmp_path, "[metrics.active_hours\n")

        with pytest.raises(toml.TomlDecodeError):
            LocalConfigCollection.from_local_path(tmp_path, strict_nimbus=True)

    def test_strict_raises_on_failed_collection_validation(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus(
            tmp_path,
            '[metrics.search_count]\ndata_source = "search_clients_engines_sources_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )

        with pytest.raises(ValueError, match="search_clients_engines_sources_daily"):
            LocalConfigCollection.from_local_path(tmp_path, strict_nimbus=True)

    def test_strict_collection_load_fails_on_an_unrelated_invalid_file(self, tmp_path):
        make_repo(tmp_path)
        write_fenix_nimbus(
            tmp_path,
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n'
            "bogus = 1\n",
        )
        Repo(tmp_path).git.add(".")
        Repo(tmp_path).git.commit("-am", "add fenix nimbus metrics")

        with pytest.raises(ValueError, match="unexpected keys"):
            ConfigCollection.from_github_repos([str(tmp_path)], strict_nimbus=True)


class TestNimbusAppLayout:
    def test_loads_defaults_file(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus_defaults_file(
            tmp_path,
            "firefox_desktop",
            '[metrics.uri_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\n'
            'column = "scalar_parent_browser_engagement_total_uri_count_sum"\n',
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)

        metric = collection.get_nimbus_metric_definition("uri_count", "firefox_desktop")
        assert metric is not None
        assert metric.aggregation == Aggregation.SUM
        assert metric.column == "scalar_parent_browser_engagement_total_uri_count_sum"

    def test_loads_outcome_file(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus_outcome_file(
            tmp_path,
            "firefox_desktop",
            "engagement",
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)

        metric = collection.get_nimbus_metric_definition("search_count", "firefox_desktop")
        assert metric is not None
        assert metric.aggregation == Aggregation.SUM

    def test_merges_definitions_defaults_and_outcomes(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus_defaults_file(
            tmp_path,
            "firefox_desktop",
            '[metrics.uri_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\n'
            'column = "scalar_parent_browser_engagement_total_uri_count_sum"\n',
        )
        write_nimbus_outcome_file(
            tmp_path,
            "firefox_desktop",
            "engagement",
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)

        assert (
            collection.get_nimbus_metric_definition("active_hours", "firefox_desktop") is not None
        )
        assert collection.get_nimbus_metric_definition("uri_count", "firefox_desktop") is not None
        assert (
            collection.get_nimbus_metric_definition("search_count", "firefox_desktop") is not None
        )
        assert {
            config.kind
            for config in collection.nimbus_configs
            if config.app_name == "firefox_desktop"
        } == {NimbusConfigKind.DEFINITIONS, NimbusConfigKind.DEFAULTS, NimbusConfigKind.OUTCOMES}

    def test_entity_from_path_defaults_file(self, tmp_path):
        write_nimbus_defaults_file(
            tmp_path,
            "firefox_desktop",
            '[metrics.uri_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\n'
            'column = "scalar_parent_browser_engagement_total_uri_count_sum"\n',
        )

        entity = entity_from_path(tmp_path / NIMBUS_DIR / "defaults" / "firefox_desktop.toml")

        assert isinstance(entity, NimbusConfig)
        assert entity.slug == "firefox_desktop"
        assert entity.app_name == "firefox_desktop"
        assert entity.kind == NimbusConfigKind.DEFAULTS
        assert "uri_count" in entity.spec.metrics

    def test_entity_from_path_outcome_file(self, tmp_path):
        write_nimbus_outcome_file(
            tmp_path,
            "firefox_desktop",
            "engagement",
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )

        entity = entity_from_path(
            tmp_path / NIMBUS_DIR / "outcomes" / "firefox_desktop" / "engagement.toml"
        )

        assert isinstance(entity, NimbusConfig)
        assert entity.slug == "engagement"
        assert entity.app_name == "firefox_desktop"
        assert entity.kind == NimbusConfigKind.OUTCOMES
        assert "search_count" in entity.spec.metrics

    def test_is_nimbus_definition(self):
        assert is_nimbus_definition(Path("nimbus") / "definitions" / "firefox_desktop.toml")
        assert is_nimbus_definition(Path("nimbus") / "defaults" / "firefox_desktop.toml")
        assert is_nimbus_definition(
            Path("nimbus") / "outcomes" / "firefox_desktop" / "engagement.toml"
        )
        assert not is_nimbus_definition(Path("nimbus") / "firefox_desktop" / "defaults.toml")
        assert not is_nimbus_definition(Path("nimbus") / "outcomes" / "engagement.toml")

    def test_duplicate_between_definitions_and_defaults_is_dropped_at_load(self, tmp_path, caplog):
        make_repo(tmp_path)
        write_nimbus_defaults_file(
            tmp_path,
            "firefox_desktop",
            '[metrics.active_hours]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "active_hours_sum"\n',
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)

        assert collection.get_nimbus_metric_definition("active_hours", "firefox_desktop") is None
        assert collection.get_nimbus_metric_definition("days_of_use", "firefox_desktop") is None
        assert any("are also defined in" in record.message for record in caplog.records)

    def test_duplicate_between_defaults_and_outcomes_is_dropped_at_load(self, tmp_path, caplog):
        make_repo(tmp_path)
        write_nimbus_defaults_file(
            tmp_path,
            "firefox_desktop",
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        write_nimbus_outcome_file(
            tmp_path,
            "firefox_desktop",
            "engagement",
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "count"\ncolumn = "sap"\n',
        )
        write_nimbus_outcome_file(
            tmp_path,
            "firefox_desktop",
            "other",
            '[metrics.other_metric]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)

        assert collection.get_nimbus_metric_definition("search_count", "firefox_desktop") is None
        assert (
            collection.get_nimbus_metric_definition("other_metric", "firefox_desktop") is not None
        )
        assert (
            collection.get_nimbus_metric_definition("active_hours", "firefox_desktop") is not None
        )
        assert any("are also defined in" in record.message for record in caplog.records)

    def test_duplicate_between_definitions_and_outcomes_is_dropped_at_load(self, tmp_path, caplog):
        make_repo(tmp_path)
        write_nimbus_outcome_file(
            tmp_path,
            "firefox_desktop",
            "engagement",
            '[metrics.active_hours]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "active_hours_sum"\n',
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)

        assert collection.get_nimbus_metric_definition("active_hours", "firefox_desktop") is None
        assert collection.get_nimbus_metric_definition("days_of_use", "firefox_desktop") is None
        assert any("are also defined in" in record.message for record in caplog.records)

    def test_duplicate_is_strict_when_checked_directly(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus_defaults_file(
            tmp_path,
            "firefox_desktop",
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        write_nimbus_outcome_file(
            tmp_path,
            "firefox_desktop",
            "engagement",
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "count"\ncolumn = "sap"\n',
        )
        Repo(tmp_path).git.add(".")
        Repo(tmp_path).git.commit("-am", "add duplicate metric across files")

        collection = ConfigCollection.from_github_repo(tmp_path, validate_nimbus=False)
        entity = entity_from_path(tmp_path / NIMBUS_DIR / "defaults" / "firefox_desktop.toml")

        with pytest.raises(ValueError, match="also defined in"):
            entity.validate(collection)

    def test_strict_raises_on_duplicate_across_defaults_and_outcomes(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus_defaults_file(
            tmp_path,
            "firefox_desktop",
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        write_nimbus_outcome_file(
            tmp_path,
            "firefox_desktop",
            "engagement",
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "count"\ncolumn = "sap"\n',
        )
        Repo(tmp_path).git.add(".")
        Repo(tmp_path).git.commit("-am", "add duplicate metric across files")

        with pytest.raises(ValueError, match="also defined in"):
            ConfigCollection.from_github_repos([str(tmp_path)], strict_nimbus=True)

    def test_aggregation_plan_across_definitions_defaults_and_outcomes(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus_defaults_file(
            tmp_path,
            "firefox_desktop",
            '[metrics.uri_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\n'
            'column = "scalar_parent_browser_engagement_total_uri_count_sum"\n',
        )
        write_nimbus_outcome_file(
            tmp_path,
            "firefox_desktop",
            "engagement",
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)

        plan = aggregation_plan(
            collection, "firefox_desktop", ["uri_count", "search_count", "active_hours"]
        )

        assert plan.missing == []
        assert set(plan.metrics) == {"uri_count", "search_count", "active_hours"}
        assert plan.sources["clients_daily"].columns == (
            "active_hours_sum",
            "sap",
            "scalar_parent_browser_engagement_total_uri_count_sum",
        )

    def test_nimbus_definition_mismatches_defaults_metric(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus_defaults_file(
            tmp_path,
            "firefox_desktop",
            '[metrics.uri_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\n'
            'column = "scalar_parent_browser_engagement_total_uri_count_sum"\n',
        )

        collection = collection_with_functions(tmp_path)

        assert collection.nimbus_definition_mismatches() == []

    def test_nimbus_definition_mismatches_reports_defaults_drift(self, tmp_path):
        make_repo(tmp_path)
        write_nimbus_defaults_file(
            tmp_path,
            "firefox_desktop",
            '[metrics.uri_count]\ndata_source = "clients_daily"\n'
            'aggregation = "count"\n'
            'column = "scalar_parent_browser_engagement_total_uri_count_sum"\n',
        )

        collection = collection_with_functions(tmp_path)

        mismatches = collection.nimbus_definition_mismatches()
        assert len(mismatches) == 1
        assert mismatches[0].metric == "uri_count"

    def test_nimbus_definition_mismatches_reports_outcome_drift_against_same_name_outcome(
        self, tmp_path
    ):
        make_repo(tmp_path)
        write_nimbus_outcome_file(
            tmp_path,
            "firefox_desktop",
            "engagement",
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )

        collection = collection_with_functions(tmp_path)
        collection.outcomes = [
            Outcome(
                slug="engagement",
                spec=OutcomeSpec(
                    friendly_name="Engagement",
                    description="Engagement",
                    metrics={
                        "search_count": parse_metric(
                            name="search_count",
                            select_expression="SUM(sap) * 2",
                        )
                    },
                ),
                platform="firefox_desktop",
                commit_hash=None,
            )
        ]

        mismatches = collection.nimbus_definition_mismatches()
        assert len(mismatches) == 1
        assert mismatches[0].metric == "search_count"
        assert mismatches[0].outcome == "engagement"


class TestNimbusDefinitionMismatches:
    def test_matching_metrics(self):
        collection = collection_with_functions(FIXTURE_DIR)

        assert collection.get_metric_definition("active_hours", "firefox_desktop") is not None
        assert collection.get_metric_definition("is_default_browser", "firefox_desktop")
        assert collection.nimbus_definition_mismatches() == []

    def test_ignores_whitespace(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        replace_active_hours_definition(
            tmp_path,
            '[metrics.active_hours]\nselect_expression = """\nCOALESCE(\n'
            '    SUM(active_hours_sum),\n    0\n)\n"""\ndata_source = "clients_daily"\n',
        )

        assert collection_with_functions(tmp_path).nimbus_definition_mismatches() == []

    def test_reports_different_select_expression(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        replace_active_hours_definition(
            tmp_path,
            ACTIVE_HOURS_DEFINITION.replace("active_hours_sum", "active_hours_sum * 2"),
        )

        assert collection_with_functions(tmp_path).nimbus_definition_mismatches() == [
            NimbusDefinitionMismatch(
                app_name="firefox_desktop",
                metric="active_hours",
                nimbus_select_expression="COALESCE(SUM(active_hours_sum), 0)",
                definitions_select_expression="COALESCE(SUM(active_hours_sum * 2), 0)",
                nimbus_data_source="clients_daily",
                definitions_data_source="clients_daily",
            )
        ]

    def test_reports_different_data_source(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        replace_active_hours_definition(
            tmp_path,
            ACTIVE_HOURS_DEFINITION.replace("clients_daily", "firefox_desktop_active_users_view"),
        )

        assert collection_with_functions(tmp_path).nimbus_definition_mismatches() == [
            NimbusDefinitionMismatch(
                app_name="firefox_desktop",
                metric="active_hours",
                nimbus_select_expression="COALESCE(SUM(active_hours_sum), 0)",
                definitions_select_expression="COALESCE(SUM(active_hours_sum), 0)",
                nimbus_data_source="clients_daily",
                definitions_data_source="firefox_desktop_active_users_view",
            )
        ]

    def test_reports_definition_without_select_expression(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        replace_active_hours_definition(
            tmp_path,
            '[metrics.active_hours]\ndepends_on = ["uri_count"]\n',
        )

        assert collection_with_functions(tmp_path).nimbus_definition_mismatches() == [
            NimbusDefinitionMismatch(
                app_name="firefox_desktop",
                metric="active_hours",
                nimbus_select_expression="COALESCE(SUM(active_hours_sum), 0)",
                definitions_select_expression=None,
                nimbus_data_source="clients_daily",
                definitions_data_source=None,
            )
        ]

    def test_matching_aggregation_fields(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        replace_active_hours_definition(
            tmp_path,
            '[metrics.active_hours]\naggregation = "sum"\ncolumn = "active_hours_sum"\n'
            'data_source = "clients_daily"\n',
        )

        assert collection_with_functions(tmp_path).nimbus_definition_mismatches() == []

    def test_reports_different_aggregation_fields(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        replace_active_hours_definition(
            tmp_path,
            '[metrics.active_hours]\naggregation = "sum"\ncolumn = "subsession_hours_sum"\n'
            'data_source = "clients_daily"\n',
        )

        assert collection_with_functions(tmp_path).nimbus_definition_mismatches() == [
            NimbusDefinitionMismatch(
                app_name="firefox_desktop",
                metric="active_hours",
                nimbus_select_expression="COALESCE(SUM(active_hours_sum), 0)",
                definitions_select_expression="COALESCE(SUM(subsession_hours_sum), 0)",
                nimbus_data_source="clients_daily",
                definitions_data_source="clients_daily",
            )
        ]

    def test_ignores_metric_only_in_nimbus(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        replace_active_hours_definition(tmp_path, "")

        collection = collection_with_functions(tmp_path)

        assert collection.get_metric_definition("active_hours", "firefox_desktop") is None
        assert collection.get_nimbus_metric_definition("active_hours", "firefox_desktop")
        assert collection.nimbus_definition_mismatches() == []

    def test_outcome_redefines_metric_sql_is_reported(self):
        collection = collection_with_functions(FIXTURE_DIR)
        collection.outcomes = [
            Outcome(
                slug="new_user_onboarding",
                spec=OutcomeSpec(
                    friendly_name="Onboarding",
                    description="Onboarding",
                    metrics={
                        "active_hours": parse_metric(
                            name="active_hours",
                            select_expression="SUM(active_hours_sum) * 2",
                        )
                    },
                ),
                platform="firefox_desktop",
                commit_hash=None,
            )
        ]

        assert collection.nimbus_definition_mismatches() == [
            NimbusDefinitionMismatch(
                app_name="firefox_desktop",
                metric="active_hours",
                nimbus_select_expression="COALESCE(SUM(active_hours_sum), 0)",
                definitions_select_expression="SUM(active_hours_sum) * 2",
                nimbus_data_source="clients_daily",
                definitions_data_source="clients_daily",
                outcome="new_user_onboarding",
            )
        ]

    def test_outcome_same_sql_is_not_reported(self):
        collection = collection_with_functions(FIXTURE_DIR)
        collection.outcomes = [
            Outcome(
                slug="new_user_onboarding",
                spec=OutcomeSpec(
                    friendly_name="Onboarding",
                    description="Onboarding",
                    metrics={
                        "active_hours": parse_metric(
                            name="active_hours",
                            select_expression="COALESCE(SUM(active_hours_sum), 0)",
                        )
                    },
                ),
                platform="firefox_desktop",
                commit_hash=None,
            )
        ]

        assert collection.nimbus_definition_mismatches() == []

    def test_outcome_statistics_only_is_not_reported(self):
        collection = collection_with_functions(FIXTURE_DIR)
        collection.outcomes = [
            Outcome(
                slug="new_user_onboarding",
                spec=OutcomeSpec(
                    friendly_name="Onboarding",
                    description="Onboarding",
                    metrics={
                        "active_hours": parse_metric(
                            name="active_hours",
                            data_source=None,
                            statistics={"bootstrap_mean": {}},
                        )
                    },
                ),
                platform="firefox_desktop",
                commit_hash=None,
            )
        ]

        assert collection.nimbus_definition_mismatches() == []

    def test_jetstream_definitions_overlay_changes_sql_is_reported(self):
        collection = collection_with_functions(FIXTURE_DIR)
        jetstream = ConfigCollection(
            definitions=[
                DefinitionConfig(
                    slug="firefox_desktop",
                    platform="firefox_desktop",
                    spec=DefinitionSpec.from_dict(
                        {
                            "metrics": {
                                "active_hours": {
                                    "select_expression": "SUM(active_hours_sum) * 2",
                                    "data_source": "clients_daily",
                                }
                            }
                        }
                    ),
                    last_modified=datetime.now(UTC),
                )
            ]
        )
        collection.merge(jetstream)

        assert collection.nimbus_definition_mismatches() == [
            NimbusDefinitionMismatch(
                app_name="firefox_desktop",
                metric="active_hours",
                nimbus_select_expression="COALESCE(SUM(active_hours_sum), 0)",
                definitions_select_expression="SUM(active_hours_sum) * 2",
                nimbus_data_source="clients_daily",
                definitions_data_source="clients_daily",
            )
        ]

    def test_ignores_metric_only_in_nimbus_with_outcomes_in_scope(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        replace_active_hours_definition(tmp_path, "")

        collection = collection_with_functions(tmp_path)
        collection.outcomes = [
            Outcome(
                slug="unrelated",
                spec=OutcomeSpec(
                    friendly_name="Unrelated",
                    description="Unrelated",
                    metrics={
                        "uri_count": parse_metric(
                            name="uri_count",
                            data_source=None,
                            statistics={"bootstrap_mean": {}},
                        )
                    },
                ),
                platform="firefox_desktop",
                commit_hash=None,
            )
        ]

        assert collection.get_metric_definition("active_hours", "firefox_desktop") is None
        assert collection.nimbus_definition_mismatches() == []

    def test_mismatch_message(self):
        mismatch = NimbusDefinitionMismatch(
            app_name="firefox_desktop",
            metric="active_hours",
            nimbus_select_expression="COALESCE(SUM(active_hours_sum), 0)",
            definitions_select_expression="SUM(active_hours_sum)",
            nimbus_data_source="clients_daily",
            definitions_data_source="clients_daily",
        )

        assert str(mismatch) == (
            "Metric 'active_hours' in nimbus/definitions/firefox_desktop.toml does not match "
            "definitions/firefox_desktop.toml\n"
            "  nimbus/definitions: data_source=clients_daily, "
            "select_expression=COALESCE(SUM(active_hours_sum), 0)\n"
            "  definitions: data_source=clients_daily, select_expression=SUM(active_hours_sum)"
        )

    def test_mismatch_message_names_outcome(self):
        mismatch = NimbusDefinitionMismatch(
            app_name="firefox_desktop",
            metric="active_hours",
            nimbus_select_expression="COALESCE(SUM(active_hours_sum), 0)",
            definitions_select_expression="SUM(active_hours_sum)",
            nimbus_data_source="clients_daily",
            definitions_data_source="clients_daily",
            outcome="new_user_onboarding",
        )

        assert str(mismatch) == (
            "Metric 'active_hours' in nimbus/definitions/firefox_desktop.toml does not match "
            "outcomes/firefox_desktop/new_user_onboarding.toml\n"
            "  nimbus/definitions: data_source=clients_daily, "
            "select_expression=COALESCE(SUM(active_hours_sum), 0)\n"
            "  outcomes/firefox_desktop/new_user_onboarding: data_source=clients_daily, "
            "select_expression=SUM(active_hours_sum)"
        )

    @pytest.mark.parametrize(
        ("sql", "expected"),
        [
            ("COUNT(x)", "COUNT(x)"),
            ("  COUNTIF(\n  a > 0\n  AND b > 0\n)  ", "COUNTIF(a > 0 AND b > 0)"),
            ("COALESCE(SUM( x ), 0)", "COALESCE(SUM(x), 0)"),
        ],
    )
    def test_normalize_sql(self, sql, expected):
        assert normalize_sql(sql) == expected


class TestNimbusExample:
    def test_example_loads(self, tmp_path):
        shutil.copytree(FIXTURE_DIR / "definitions", tmp_path / "definitions")
        write_nimbus(tmp_path, EXAMPLE_FILE.read_text())

        collection = LocalConfigCollection.from_local_path(tmp_path)

        metrics = collection.nimbus_configs[0].spec.metrics
        assert {metric.aggregation for metric in metrics.values()} == set(Aggregation)

    def test_example_uses_every_field(self):
        metrics = toml.load(EXAMPLE_FILE)["metrics"]

        assert set().union(*metrics.values()) == NIMBUS_METRIC_KEYS
