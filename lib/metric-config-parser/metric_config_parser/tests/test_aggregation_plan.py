import shutil
from pathlib import Path

from metric_config_parser.aggregation import Combine
from metric_config_parser.aggregation_plan import aggregation_plan
from metric_config_parser.config import LocalConfigCollection

TEST_DIR = Path(__file__).parent
FIXTURE_DIR = TEST_DIR / "data" / "nimbus_repo"


def load_collection():
    return LocalConfigCollection.from_local_path(FIXTURE_DIR)


class TestAggregationPlan:
    def test_missing_metric_names_are_reported_not_raised(self):
        collection = load_collection()

        plan = aggregation_plan(collection, "firefox_desktop", ["not_a_real_metric"])

        assert plan.missing == ["not_a_real_metric"]
        assert plan.metrics == {}
        assert plan.sources == {}

    def test_two_metrics_sharing_one_source_group_together(self):
        collection = load_collection()

        plan = aggregation_plan(collection, "firefox_desktop", ["active_hours", "days_of_use"])

        assert set(plan.sources) == {"clients_daily"}
        assert plan.metrics["active_hours"].data_source == "clients_daily"
        assert plan.metrics["days_of_use"].data_source == "clients_daily"

    def test_source_columns_are_the_union_including_a_where_metric(self):
        collection = load_collection()

        plan = aggregation_plan(
            collection,
            "firefox_desktop",
            ["active_hours", "days_of_use", "qualified_cumulative_days_of_use"],
        )

        source = plan.sources["clients_daily"]
        assert source.from_expression == "mozdata.telemetry.clients_daily"
        assert source.client_id_column == "client_id"
        assert source.group_id_column == "profile_group_id"
        assert source.analysis_units == ("client_id", "profile_group_id")
        assert source.submission_date_column == "submission_date"
        assert source.columns == (
            "active_hours_sum",
            "scalar_parent_browser_engagement_total_uri_count_normal_and_private_mode_sum",
            "submission_date",
        )

    def test_source_grouping_separates_metrics_on_different_sources(self):
        collection = load_collection()

        plan = aggregation_plan(
            collection, "firefox_desktop", ["active_hours", "active_in_last_3_days_legacy"]
        )

        assert set(plan.sources) == {"clients_daily", "firefox_desktop_active_users_view"}
        assert plan.sources["clients_daily"].columns == ("active_hours_sum",)
        assert plan.sources["firefox_desktop_active_users_view"].columns == ("days_active_bits",)

    def test_cumulative_window_fields_pass_through(self):
        collection = load_collection()

        plan = aggregation_plan(collection, "firefox_desktop", ["active_hours"])

        metric = plan.metrics["active_hours"]
        assert metric.cumulative_window == 7
        assert metric.incremental_window is None
        assert metric.repeat_windows is True
        assert metric.aggregation.bucket_aggregate == "COALESCE(SUM(active_hours_sum), 0)"
        assert metric.aggregation.combine == Combine.SUM

    def test_incremental_window_fields_pass_through(self):
        collection = load_collection()

        plan = aggregation_plan(collection, "firefox_desktop", ["retained"])

        metric = plan.metrics["retained"]
        assert metric.cumulative_window is None
        assert metric.incremental_window == 7
        assert metric.repeat_windows is True

    def test_any_with_column_shorthand_bucketed_aggregation(self):
        collection = load_collection()

        plan = aggregation_plan(collection, "firefox_desktop", ["is_default_browser"])

        metric = plan.metrics["is_default_browser"]
        assert metric.aggregation.bucket_aggregate == "COUNTIF(is_default_browser)"
        assert metric.aggregation.finalize == "CAST({combined} > 0 AS INT64)"

    def test_recency_within_bucketed_aggregation(self):
        collection = load_collection()

        plan = aggregation_plan(collection, "firefox_desktop", ["active_in_last_3_days_legacy"])

        metric = plan.metrics["active_in_last_3_days_legacy"]
        assert metric.aggregation.combine == Combine.MIN
        assert metric.aggregation.no_rows == "30"
        assert metric.aggregation.finalize == "CAST({combined} < 3 AS INT64)"

    def test_resolved_and_missing_names_can_be_requested_together(self):
        collection = load_collection()

        plan = aggregation_plan(
            collection, "firefox_desktop", ["active_hours", "not_a_real_metric"]
        )

        assert plan.missing == ["not_a_real_metric"]
        assert set(plan.metrics) == {"active_hours"}

    def test_dotted_column_contributes_its_full_path(self):
        collection = load_collection()

        plan = aggregation_plan(collection, "firefox_desktop", ["glean_counter_example"])

        source = plan.sources["clients_daily"]
        assert source.columns == ("metrics.counter.example_counter",)

    def test_dotted_column_shares_a_source_with_a_plain_column(self):
        collection = load_collection()

        plan = aggregation_plan(
            collection, "firefox_desktop", ["glean_counter_example", "active_hours"]
        )

        source = plan.sources["clients_daily"]
        assert source.columns == ("active_hours_sum", "metrics.counter.example_counter")

    def test_resolves_metric_using_data_source_declared_in_nimbus(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        nimbus_file = tmp_path / "nimbus" / "definitions" / "firefox_desktop.toml"
        nimbus_file.write_text(
            f"{nimbus_file.read_text()}\n[data_sources.nimbus_only_source]\n"
            'from_expression = "mozdata.foo.bar"\n'
            'submission_date_column = "submission_date"\n\n'
            "[metrics.nimbus_sourced_metric]\n"
            'data_source = "nimbus_only_source"\n'
            'aggregation = "sum"\n'
            'column = "x"\n'
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)
        plan = aggregation_plan(collection, "firefox_desktop", ["nimbus_sourced_metric"])

        assert plan.missing == []
        assert plan.sources["nimbus_only_source"].from_expression == "mozdata.foo.bar"
        assert plan.metrics["nimbus_sourced_metric"].data_source == "nimbus_only_source"

    def test_plan_ordering_is_deterministic(self):
        collection = load_collection()

        plan = aggregation_plan(
            collection,
            "firefox_desktop",
            ["retained", "active_hours", "days_of_use", "qualified_cumulative_days_of_use"],
        )

        assert list(plan.metrics) == sorted(plan.metrics)
        assert list(plan.sources) == sorted(plan.sources)

    def test_is_binary_false_for_plain_sum(self):
        collection = load_collection()

        plan = aggregation_plan(collection, "firefox_desktop", ["active_hours"])

        assert plan.metrics["active_hours"].is_binary is False

    def test_is_binary_false_for_count_and_count_where(self):
        collection = load_collection()

        plan = aggregation_plan(
            collection,
            "firefox_desktop",
            ["days_of_use", "qualified_cumulative_days_of_use"],
        )

        assert plan.metrics["days_of_use"].is_binary is False
        assert plan.metrics["qualified_cumulative_days_of_use"].is_binary is False

    def test_is_binary_true_for_any(self):
        collection = load_collection()

        plan = aggregation_plan(collection, "firefox_desktop", ["is_default_browser"])

        assert plan.metrics["is_default_browser"].is_binary is True

    def test_is_binary_true_for_recency_within(self):
        collection = load_collection()

        plan = aggregation_plan(collection, "firefox_desktop", ["active_in_last_3_days_legacy"])

        assert plan.metrics["active_in_last_3_days_legacy"].is_binary is True

    def test_is_binary_true_for_sum_with_threshold(self):
        collection = load_collection()

        plan = aggregation_plan(collection, "firefox_desktop", ["retained"])

        assert plan.metrics["retained"].is_binary is True

    def test_winsorize_fields_default_to_none(self):
        collection = load_collection()

        plan = aggregation_plan(collection, "firefox_desktop", ["active_hours"])

        metric = plan.metrics["active_hours"]
        assert metric.winsorize_quantile is None
        assert metric.winsorize_threshold is None

    def test_winsorize_quantile_passes_through_unchanged(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        nimbus_file = tmp_path / "nimbus" / "definitions" / "firefox_desktop.toml"
        nimbus_file.write_text(
            nimbus_file.read_text().replace(
                "[metrics.glean_counter_example]",
                "[metrics.glean_counter_example]\nwinsorize_quantile = 0.995",
            )
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)
        plan = aggregation_plan(collection, "firefox_desktop", ["glean_counter_example"])

        assert plan.metrics["glean_counter_example"].winsorize_quantile == 0.995
        assert plan.metrics["glean_counter_example"].winsorize_threshold is None

    def test_winsorize_quantile_one_is_preserved_as_explicitly_off(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        nimbus_file = tmp_path / "nimbus" / "definitions" / "firefox_desktop.toml"
        nimbus_file.write_text(
            nimbus_file.read_text().replace(
                "[metrics.glean_counter_example]",
                "[metrics.glean_counter_example]\nwinsorize_quantile = 1",
            )
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)
        plan = aggregation_plan(collection, "firefox_desktop", ["glean_counter_example"])

        metric = plan.metrics["glean_counter_example"]
        assert metric.winsorize_quantile == 1
        assert metric.winsorize_quantile is not None

    def test_winsorize_threshold_passes_through_unchanged(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        nimbus_file = tmp_path / "nimbus" / "definitions" / "firefox_desktop.toml"
        nimbus_file.write_text(
            nimbus_file.read_text().replace(
                "[metrics.glean_counter_example]",
                "[metrics.glean_counter_example]\nwinsorize_threshold = 500",
            )
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)
        plan = aggregation_plan(collection, "firefox_desktop", ["glean_counter_example"])

        assert plan.metrics["glean_counter_example"].winsorize_threshold == 500
        assert plan.metrics["glean_counter_example"].winsorize_quantile is None

    def test_winsorize_fields_do_not_change_generated_sql(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        nimbus_file = tmp_path / "nimbus" / "definitions" / "firefox_desktop.toml"
        nimbus_file.write_text(
            nimbus_file.read_text().replace(
                "[metrics.glean_counter_example]",
                "[metrics.glean_counter_example]\nwinsorize_quantile = 0.995",
            )
        )

        without_winsorize = load_collection()
        with_winsorize = LocalConfigCollection.from_local_path(tmp_path)

        plan_without = aggregation_plan(
            without_winsorize, "firefox_desktop", ["glean_counter_example"]
        )
        plan_with = aggregation_plan(with_winsorize, "firefox_desktop", ["glean_counter_example"])

        assert (
            plan_without.metrics["glean_counter_example"].aggregation
            == plan_with.metrics["glean_counter_example"].aggregation
        )
