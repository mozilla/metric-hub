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

    def test_plan_ordering_is_deterministic(self):
        collection = load_collection()

        plan = aggregation_plan(
            collection,
            "firefox_desktop",
            ["retained", "active_hours", "days_of_use", "qualified_cumulative_days_of_use"],
        )

        assert list(plan.metrics) == sorted(plan.metrics)
        assert list(plan.sources) == sorted(plan.sources)
