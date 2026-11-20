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


class TestColumnFormSource:
    def test_map_column_source_is_the_map_not_the_expression(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        nimbus_file = tmp_path / "nimbus" / "definitions" / "firefox_desktop.toml"
        map_column = "metrics.labeled_counter.cert_verifier_cert_revocation_mechanisms"
        nimbus_file.write_text(
            f"{nimbus_file.read_text()}\n"
            "[metrics.crlite_use_counter]\n"
            'data_source = "clients_daily"\n'
            'aggregation = "sum"\n'
            f'column = {{ map = "{map_column}", key = "CRLite" }}\n'
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)
        plan = aggregation_plan(collection, "firefox_desktop", ["crlite_use_counter"])

        assert plan.sources["clients_daily"].columns == (
            "metrics.labeled_counter.cert_verifier_cert_revocation_mechanisms",
        )
        assert plan.metrics["crlite_use_counter"].aggregation.bucket_aggregate == (
            "COALESCE(SUM(mozfun.map.get_key(metrics.labeled_counter."
            "cert_verifier_cert_revocation_mechanisms, 'CRLite')), 0)"
        )

    def test_json_column_source_in_a_condition(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        nimbus_file = tmp_path / "nimbus" / "definitions" / "firefox_desktop.toml"
        nimbus_file.write_text(
            f"{nimbus_file.read_text()}\n"
            "[metrics.pin_prompt_accepted]\n"
            'data_source = "clients_daily"\n'
            'aggregation = "any"\n\n'
            "[[metrics.pin_prompt_accepted.where]]\n"
            'column = { json = "event_extra", path = "result" }\n'
            'op = "="\n'
            'value = "success_pinned"\n'
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)
        plan = aggregation_plan(collection, "firefox_desktop", ["pin_prompt_accepted"])

        assert plan.sources["clients_daily"].columns == ("event_extra",)


class TestConditionOperatorSource:
    def test_any_of_contributes_every_clause_column(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        nimbus_file = tmp_path / "nimbus" / "definitions" / "firefox_desktop.toml"
        nimbus_file.write_text(
            f"{nimbus_file.read_text()}\n"
            "[metrics.site_breakage_uses]\n"
            'data_source = "clients_daily"\n'
            'aggregation = "any"\n\n'
            "[[metrics.site_breakage_uses.where]]\n"
            "any_of = [\n"
            '  { column = "event_name", op = "=", value = "send" },\n'
            '  { column = "event_category", op = "=", value = "send_more_info" },\n'
            "]\n"
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)
        plan = aggregation_plan(collection, "firefox_desktop", ["site_breakage_uses"])

        assert plan.sources["clients_daily"].columns == ("event_category", "event_name")

    def test_like_and_in_columns_are_the_underlying_column(self, tmp_path):
        shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
        nimbus_file = tmp_path / "nimbus" / "definitions" / "firefox_desktop.toml"
        nimbus_file.write_text(
            f"{nimbus_file.read_text()}\n"
            "[metrics.pip_disabled]\n"
            'data_source = "clients_daily"\n'
            'aggregation = "count_where"\n'
            'threshold = { op = ">", value = 0 }\n\n'
            "[[metrics.pip_disabled.where]]\n"
            'column = "event_category"\n'
            'op = "="\n'
            'value = "pictureinpicture"\n\n'
            "[[metrics.pip_disabled.where]]\n"
            'column = "event_name"\n'
            'op = "LIKE"\n'
            'value = "%disable%"\n'
        )

        collection = LocalConfigCollection.from_local_path(tmp_path)
        plan = aggregation_plan(collection, "firefox_desktop", ["pip_disabled"])

        assert plan.sources["clients_daily"].columns == ("event_category", "event_name")
