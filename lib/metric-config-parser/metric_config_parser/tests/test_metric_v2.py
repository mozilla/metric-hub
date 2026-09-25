import shutil
from pathlib import Path

import pytest
import toml
from git import Repo

from metric_config_parser.config import (
    ConfigCollection,
    LocalConfigCollection,
    MetricV2Config,
    entity_from_path,
)
from metric_config_parser.metric_v2 import (
    METRIC_KEYS,
    METRIC_V2_DIR,
    Aggregation,
    Clause,
    MetricV2Definition,
    MetricV2Spec,
    Operator,
    Threshold,
)

TEST_DIR = Path(__file__).parent
FIXTURE_DIR = TEST_DIR / "data" / "metric_v2"
V2_FILE = FIXTURE_DIR / METRIC_V2_DIR / "firefox_desktop.toml"
EXAMPLE_FILE = TEST_DIR.parents[3] / METRIC_V2_DIR / "example_config.toml.example"


def make_repo(tmp_path, source=FIXTURE_DIR):
    shutil.copytree(source, tmp_path, dirs_exist_ok=True)
    r = Repo.init(tmp_path)
    r.config_writer().set_value("user", "name", "test").release()
    r.config_writer().set_value("user", "email", "test@example.com").release()
    r.config_writer().set_value("commit", "gpgsign", "false").release()
    r.git.add(".")
    r.git.commit("-m", "commit")
    return tmp_path


def write_v2(root, metrics_toml):
    v2_dir = root / METRIC_V2_DIR
    v2_dir.mkdir(parents=True, exist_ok=True)
    (v2_dir / "firefox_desktop.toml").write_text(metrics_toml)


def parse_metric(**fields):
    return MetricV2Definition.from_dict("m", {"data_source": "clients_daily", **fields})


class TestMetricV2Spec:
    def test_from_file(self):
        spec = MetricV2Spec.from_file(V2_FILE)

        assert spec.dataset == "firefox_desktop"
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
        metric = MetricV2Spec.from_file(V2_FILE).metrics["active_hours"]

        assert metric.name == "active_hours"
        assert metric.data_source == "clients_daily"
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
        metric = MetricV2Spec.from_file(V2_FILE).metrics["retained"]

        assert metric.aggregation == Aggregation.SUM
        assert metric.column == "pings_aggregated_by_this_row"
        assert metric.threshold == Threshold(op=Operator.GT, value=0)
        assert metric.cumulative_window is None
        assert metric.incremental_window == 7
        assert metric.repeat_windows is True

    def test_count_where_with_clauses(self):
        metric = MetricV2Spec.from_file(V2_FILE).metrics["qualified_cumulative_days_of_use"]

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
        metric = MetricV2Spec.from_file(V2_FILE).metrics["is_default_browser"]

        assert metric.aggregation == Aggregation.ANY
        assert metric.column == "is_default_browser"
        assert metric.where == []
        assert metric.conditions == [Clause(column="is_default_browser")]

    def test_recency_within(self):
        metric = MetricV2Spec.from_file(V2_FILE).metrics["active_in_last_3_days_legacy"]

        assert metric.aggregation == Aggregation.RECENCY_WITHIN
        assert metric.column == "days_active_bits"
        assert metric.within_days == 3

    def test_count_where_with_scale(self):
        metric = MetricV2Spec.from_file(V2_FILE).metrics[
            "daily_active_users_per_1000_clients_legacy"
        ]

        assert metric.aggregation == Aggregation.COUNT_WHERE
        assert metric.conditions == [Clause(column="is_dau")]
        assert metric.scale == 1000

    def test_count(self):
        metric = MetricV2Spec.from_file(V2_FILE).metrics["days_of_use"]

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


class TestMetricV2Rejections:
    @pytest.mark.parametrize(
        ("fields", "match"),
        [
            ({"aggregation": "count_distinct", "column": "a"}, "is not one of"),
            ({"aggregation": "average", "column": "a"}, "is not one of"),
            ({"column": "a"}, "aggregation is required"),
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
                {"aggregation": "sum", "column": "a", "windows": ["cumulative_weekly"]},
                "unexpected keys",
            ),
            (
                {"aggregation": "sum", "column": "a", "disjoint_window": 7},
                "unexpected keys",
            ),
            (
                {"aggregation": "sum", "column": "a", "statistics": {"bootstrap_mean": 1}},
                "table of tables",
            ),
            (
                {"aggregation": "sum", "column": "a", "select_expression": "SUM(a)"},
                "unexpected keys",
            ),
        ],
    )
    def test_rejects(self, fields, match):
        with pytest.raises(ValueError, match=match):
            parse_metric(**fields)

    def test_rejects_missing_data_source(self):
        with pytest.raises(ValueError, match="data_source"):
            MetricV2Definition.from_dict("m", {"aggregation": "sum", "column": "a"})

    def test_rejects_unknown_top_level_key(self):
        with pytest.raises(ValueError, match="data_sources"):
            MetricV2Spec.from_dict({"metrics": {}, "data_sources": {}}, "firefox_desktop")

    def test_direct_construction_validates(self):
        with pytest.raises(ValueError, match="requires a column"):
            MetricV2Definition(name="m", data_source="clients_daily", aggregation=Aggregation.SUM)

    def test_invalid_file_fails_to_load(self, tmp_path):
        make_repo(tmp_path)
        write_v2(
            tmp_path,
            '[metrics.bad]\ndata_source = "clients_daily"\naggregation = "sum"\n',
        )

        with pytest.raises(ValueError, match="requires a column"):
            LocalConfigCollection.from_local_path(tmp_path)


class TestMetricV2Collection:
    def test_loads_from_local_repo(self, tmp_path):
        collection = ConfigCollection.from_github_repo(make_repo(tmp_path))

        assert len(collection.definitions) == 1
        assert len(collection.metric_v2_configs) == 1
        config = collection.metric_v2_configs[0]
        assert config.slug == "firefox_desktop"
        assert config.spec == MetricV2Spec.from_file(V2_FILE)

    def test_loads_from_local_path(self):
        collection = LocalConfigCollection.from_local_path(FIXTURE_DIR)

        assert [config.slug for config in collection.metric_v2_configs] == ["firefox_desktop"]
        assert "active_hours" in collection.metric_v2_configs[0].spec.metrics

    def test_no_v2_directory(self, config_collection):
        assert config_collection.metric_v2_configs == []

    def test_entity_from_path(self):
        entity = entity_from_path(V2_FILE)

        assert isinstance(entity, MetricV2Config)
        assert entity.slug == "firefox_desktop"
        assert entity.spec == MetricV2Spec.from_file(V2_FILE)

    def test_entity_validates_against_collection(self):
        collection = LocalConfigCollection.from_local_path(FIXTURE_DIR)

        entity_from_path(V2_FILE).validate(collection)

    def test_merge(self, tmp_path):
        base = make_repo(tmp_path / "base")
        override = make_repo(tmp_path / "override")
        write_v2(
            override,
            '[metrics.search_count]\ndata_source = "clients_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )
        Repo(override).git.commit("-am", "replace v2 metrics")

        collection = ConfigCollection.from_github_repo(base)
        collection.merge(ConfigCollection.from_github_repo(override))

        assert len(collection.metric_v2_configs) == 1
        assert set(collection.metric_v2_configs[0].spec.metrics) == {"search_count"}

    def test_merge_keeps_configs_for_other_apps(self, tmp_path):
        collection = ConfigCollection.from_github_repo(make_repo(tmp_path))
        other = ConfigCollection(
            metric_v2_configs=[
                MetricV2Config(slug="fenix", spec=MetricV2Spec(dataset="fenix", metrics={}))
            ]
        )

        collection.merge(other)

        assert sorted(config.slug for config in collection.metric_v2_configs) == [
            "fenix",
            "firefox_desktop",
        ]

    def test_rejects_undefined_data_source(self, tmp_path):
        make_repo(tmp_path)
        write_v2(
            tmp_path,
            '[metrics.search_count]\ndata_source = "search_clients_engines_sources_daily"\n'
            'aggregation = "sum"\ncolumn = "sap"\n',
        )

        with pytest.raises(ValueError, match="search_clients_engines_sources_daily"):
            LocalConfigCollection.from_local_path(tmp_path)

    def test_rejects_data_source_from_another_app(self, tmp_path):
        make_repo(tmp_path)
        v2_dir = tmp_path / METRIC_V2_DIR
        (v2_dir / "firefox_desktop.toml").rename(v2_dir / "fenix.toml")

        with pytest.raises(ValueError, match=r"not defined in definitions/fenix\.toml"):
            LocalConfigCollection.from_local_path(tmp_path)

    def test_rejects_metric_defined_in_v1_and_v2(self, tmp_path):
        make_repo(tmp_path)
        v2 = toml.load(V2_FILE)
        v2["metrics"]["uri_count"] = {
            "data_source": "clients_daily",
            "aggregation": "sum",
            "column": "scalar_parent_browser_engagement_total_uri_count_sum",
        }
        write_v2(tmp_path, toml.dumps(v2))
        Repo(tmp_path).git.commit("-am", "port uri_count")

        with pytest.raises(ValueError, match="'uri_count' is defined in both"):
            ConfigCollection.from_github_repo(tmp_path)


class TestMetricV2Example:
    def test_example_loads(self, tmp_path):
        shutil.copytree(FIXTURE_DIR / "definitions", tmp_path / "definitions")
        write_v2(tmp_path, EXAMPLE_FILE.read_text())

        collection = LocalConfigCollection.from_local_path(tmp_path)

        metrics = collection.metric_v2_configs[0].spec.metrics
        assert {metric.aggregation for metric in metrics.values()} == set(Aggregation)

    def test_example_uses_every_field(self):
        metrics = toml.load(EXAMPLE_FILE)["metrics"]

        assert set().union(*metrics.values()) == METRIC_KEYS
