from textwrap import dedent

import pytest
import toml
from cattrs.errors import ClassValidationError

from metric_config_parser.analysis import AnalysisSpec
from metric_config_parser.experiment import Experiment
from metric_config_parser.segment import (
    SegmentDataSourceDefinition,
    SegmentDataSourceReference,
    SegmentDefinition,
)


class TestSegments:
    def test_segments_resolved(self):
        config_str = dedent(
            '''
            [segments.new_or_resurrected_v3]
            data_source = "clients_last_seen"
            select_expression = "LOGICAL_OR(COALESCE(is_new_or_resurrected_v3, TRUE))"
            friendly_name = "New or resurrected users (v3)"
            description = """
                Clients who used Firefox on none of the 27 days prior to enrolling.
            """

            [segments.data_sources.clients_last_seen]
            from_expression = "mozdata.telemetry.clients_last_seen"
            window_start = 0
            window_end = 0
            '''
        )
        analysis_spec = AnalysisSpec.from_dict(toml.loads(config_str))

        assert "new_or_resurrected_v3" in analysis_spec.segments.definitions

        segment_definition = analysis_spec.segments.definitions["new_or_resurrected_v3"]
        assert segment_definition.name == "new_or_resurrected_v3"
        assert segment_definition.data_source.name == "clients_last_seen"
        expected_expression = "LOGICAL_OR(COALESCE(is_new_or_resurrected_v3, TRUE))"
        assert segment_definition.select_expression == expected_expression
        assert segment_definition.friendly_name == "New or resurrected users (v3)"
        assert "none of the 27 days" in segment_definition.description

        assert "clients_last_seen" in analysis_spec.segments.data_sources

        data_source_definition = analysis_spec.segments.data_sources["clients_last_seen"]
        assert data_source_definition.name == "clients_last_seen"
        assert data_source_definition.from_expression == "mozdata.telemetry.clients_last_seen"
        assert data_source_definition.window_start == 0
        assert data_source_definition.window_end == 0

    def test_segments_merge(self):
        config_str_1 = dedent(
            """
            [segments.regular_users]
            data_source = "clients_last_seen"
            select_expression = "LOGICAL_OR(is_regular_user)"
            friendly_name = "Regular Users"
            description = "Clients who regularly use Firefox."

            [segments.data_sources.clients_last_seen]
            from_expression = "mozdata.telemetry.clients_last_seen"
            window_start = -7
            window_end = 0
            """
        )
        config_str_2 = dedent(
            """
            [segments.new_users]
            data_source = "clients_first_seen"
            select_expression = "LOGICAL_OR(is_new_user)"
            friendly_name = "New Users"
            description = "Clients who are new to Firefox."

            [segments.data_sources.clients_first_seen]
            from_expression = "mozdata.telemetry.clients_first_seen"
            window_start = -30
            window_end = 0
            """
        )

        analysis_spec_1 = AnalysisSpec.from_dict(toml.loads(config_str_1))
        analysis_spec_2 = AnalysisSpec.from_dict(toml.loads(config_str_2))

        analysis_spec_1.segments.merge(analysis_spec_2.segments)

        assert "regular_users" in analysis_spec_1.segments.definitions
        assert "new_users" in analysis_spec_1.segments.definitions

        assert analysis_spec_1.segments.definitions["regular_users"].name == "regular_users"
        assert analysis_spec_1.segments.definitions["new_users"].name == "new_users"

        assert "clients_last_seen" in analysis_spec_1.segments.data_sources
        assert "clients_first_seen" in analysis_spec_1.segments.data_sources

    def test_missing_data_source(self):
        config_str = dedent(
            """
            [segments.no_data_source]
            select_expression = "LOGICAL_OR(is_no_data_source)"
            friendly_name = "No Data Source"
            description = "This segment is missing a data source."
            """
        )

        with pytest.raises(ClassValidationError):
            AnalysisSpec.from_dict(toml.loads(config_str))

    def test_segments_not_defined(self):
        config_str = dedent(
            """
            [metrics]
            weekly = ["metric1"]
            """
        )

        analysis_spec = AnalysisSpec.from_dict(toml.loads(config_str))

        assert analysis_spec.segments.definitions == {}

    def test_segment_resolution_and_merge(self, experiments, config_collection):
        spec = AnalysisSpec()

        spec.resolve(experiments[9], config_collection)

        assert "regular_users_v3" in spec.segments.definitions
        assert spec.segments.definitions["regular_users_v3"].name == "regular_users_v3"

    def test_segments_with_different_data_sources(self, config_collection):
        segment_definitions = {
            "segment_a": SegmentDefinition(
                name="segment_a",
                data_source=SegmentDataSourceReference(name="data_source_a"),
                select_expression="expression_a",
            ),
            "segment_b": SegmentDefinition(
                name="segment_b",
                data_source=SegmentDataSourceReference(name="data_source_b"),
                select_expression="expression_b",
            ),
        }

        def mock_get_segment_definition(slug, app_name):
            if slug in segment_definitions and app_name == "test_app":
                return segment_definitions[slug]
            return None

        config_collection.get_segment_definition = mock_get_segment_definition

        data_source_definitions = {
            "data_source_a": SegmentDataSourceDefinition(
                name="data_source_a",
                from_expression="from_expression_a",
            ),
            "data_source_b": SegmentDataSourceDefinition(
                name="data_source_b",
                from_expression="from_expression_b",
            ),
        }

        def mock_get_segment_data_source_definition(name, app_name):
            if name in data_source_definitions and app_name == "test_app":
                return data_source_definitions[name]
            return None

        config_collection.get_segment_data_source_definition = (
            mock_get_segment_data_source_definition
        )

        experiment = Experiment(
            experimenter_slug="test_experiment",
            type="test",
            status="Live",
            start_date="2021-01-01",
            end_date="2021-02-01",
            proposed_enrollment=1000,
            branches=[],
            normandy_slug="test_normandy_slug",
            reference_branch=None,
            is_high_population=False,
            outcomes=[],
            app_name="test_app",
            segments=["segment_a", "segment_b"],
        )

        spec = AnalysisSpec()
        cfg = spec.resolve(experiment, config_collection)

        for slug in ["segment_a", "segment_b"]:
            assert slug in spec.segments.definitions
            segment_def = spec.segments.definitions[slug]
            data_source_ref = segment_def.data_source
            data_source = data_source_ref.resolve(spec, cfg.experiment, config_collection)
            assert data_source.name == segment_def.data_source.name
            assert data_source.from_expression == f"from_expression_{slug[-1]}"
