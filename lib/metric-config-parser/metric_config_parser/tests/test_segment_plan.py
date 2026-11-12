from pathlib import Path

import pytest
from jinja2 import UndefinedError

from metric_config_parser.config import LocalConfigCollection
from metric_config_parser.segment_plan import segment_plan

TEST_DIR = Path(__file__).parent
FIXTURE_DIR = TEST_DIR / "data" / "nimbus_repo"


def load_collection():
    return LocalConfigCollection.from_local_path(FIXTURE_DIR)


class TestSegmentPlan:
    def test_missing_segment_names_are_reported_not_raised(self):
        collection = load_collection()

        plan = segment_plan(collection, "firefox_desktop", ["not_a_real_segment"])

        assert plan.missing == ["not_a_real_segment"]
        assert plan.segments == {}
        assert plan.sources == {}

    def test_two_segments_sharing_one_source_group_together(self):
        collection = load_collection()

        plan = segment_plan(collection, "firefox_desktop", ["regular_user", "new_profile"])

        assert set(plan.sources) == {"clients_last_seen"}
        assert plan.segments["regular_user"].data_source == "clients_last_seen"
        assert plan.segments["new_profile"].data_source == "clients_last_seen"

    def test_source_grouping_separates_segments_on_different_sources(self):
        collection = load_collection()

        plan = segment_plan(collection, "firefox_desktop", ["regular_user", "suggest_user"])

        assert set(plan.sources) == {"clients_last_seen", "newtab"}

    def test_rendered_select_expression(self):
        collection = load_collection()

        plan = segment_plan(collection, "firefox_desktop", ["regular_user"])

        segment = plan.segments["regular_user"]
        assert segment.select_expression == "COALESCE(LOGICAL_OR(is_regular_user_v3), FALSE)"

    def test_source_window_and_unit_columns_pass_through(self):
        collection = load_collection()

        plan = segment_plan(collection, "firefox_desktop", ["regular_user", "suggest_user"])

        default_window_source = plan.sources["clients_last_seen"]
        assert default_window_source.from_expression == "mozdata.telemetry.clients_last_seen"
        assert default_window_source.window_start == 0
        assert default_window_source.window_end == 0
        assert default_window_source.client_id_column == "client_id"
        assert default_window_source.group_id_column == "profile_group_id"
        assert default_window_source.submission_date_column == "submission_date"

        custom_window_source = plan.sources["newtab"]
        assert custom_window_source.window_start == -7
        assert custom_window_source.window_end == -1

    def test_resolved_and_missing_names_can_be_requested_together(self):
        collection = load_collection()

        plan = segment_plan(collection, "firefox_desktop", ["regular_user", "not_a_real_segment"])

        assert plan.missing == ["not_a_real_segment"]
        assert set(plan.segments) == {"regular_user"}

    def test_plan_ordering_is_deterministic(self):
        collection = load_collection()

        plan = segment_plan(
            collection, "firefox_desktop", ["suggest_user", "regular_user", "new_profile"]
        )

        assert list(plan.segments) == sorted(plan.segments)
        assert list(plan.sources) == sorted(plan.sources)

    def test_templated_from_expression_raises(self):
        collection = load_collection()

        with pytest.raises(UndefinedError):
            segment_plan(collection, "firefox_desktop", ["templated_segment"])
