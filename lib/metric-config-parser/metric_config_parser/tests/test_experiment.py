import datetime as dt
from pathlib import Path
from textwrap import dedent

import pytest
import pytz
import toml
from cattrs.errors import ClassValidationError
from mozilla_nimbus_schemas import RandomizationUnit

from metric_config_parser import AnalysisUnit
from metric_config_parser.analysis import AnalysisSpec
from metric_config_parser.errors import NoEndDateException
from metric_config_parser.experiment import Branch, BucketConfig, Experiment
from metric_config_parser.metric import AnalysisPeriod
from metric_config_parser.segment import Segment

TEST_DIR = Path(__file__).parent
DEFAULT_METRICS_CONFIG = TEST_DIR / "data" / "jetstream" / "defaults" / "firefox_desktop.toml"


class TestExperimentSpec:
    def test_null_query(self, experiments, config_collection):
        spec = AnalysisSpec.from_dict({})
        cfg = spec.resolve(experiments[0], config_collection)
        assert cfg.experiment.enrollment_query is None

    def test_trivial_query(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            enrollment_query = "SELECT 1"
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        cfg = spec.resolve(experiments[0], config_collection)
        assert cfg.experiment.enrollment_query == "SELECT 1"

    def test_template_query(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            enrollment_query = "SELECT 1 FROM foo WHERE slug = '{{experiment.experimenter_slug}}'"
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        cfg = spec.resolve(experiments[0], config_collection)
        assert cfg.experiment.enrollment_query == "SELECT 1 FROM foo WHERE slug = 'test_slug'"

    def test_silly_query(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            enrollment_query = "{{experiment.enrollment_query}}"  # whoa
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        with pytest.raises(ValueError):
            spec.resolve(experiments[0], config_collection)

    def test_control_branch(self, experiments, config_collection):
        trivial = AnalysisSpec().resolve(experiments[0], config_collection)
        assert trivial.experiment.reference_branch == "b"

        conf = dedent(
            """
            [experiment]
            reference_branch = "a"
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        configured = spec.resolve(experiments[0], config_collection)
        assert configured.experiment.reference_branch == "a"

    def test_recognizes_segments(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            segments = ["regular_users_v3"]
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        configured = spec.resolve(experiments[0], config_collection)
        assert isinstance(configured.experiment.segments[0], Segment)

    def test_segment_definitions(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            segments = ["regular_users_v3", "my_cool_segment"]

            [segments.my_cool_segment]
            Data_Source = "my_cool_data_source"
            Select_Expression = "{{agg_any('1')}}"

            [segments.data_sources.my_cool_data_source]
            from_expression = "(SELECT 1 WHERE submission_date BETWEEN {{experiment.start_date_str}} AND {{experiment.last_enrollment_date_str}})"
            """  # noqa
        )

        spec = AnalysisSpec.from_dict(toml.loads(conf))
        configured = spec.resolve(experiments[0], config_collection)

        assert len(configured.experiment.segments) == 2

        for segment in configured.experiment.segments:
            assert isinstance(segment, Segment)

        assert configured.experiment.segments[0].name == "regular_users_v3"
        assert configured.experiment.segments[1].name == "my_cool_segment"

        assert "agg_any" not in configured.experiment.segments[1].select_expression
        assert "1970" not in configured.experiment.segments[1].data_source.from_expression
        assert "{{" not in configured.experiment.segments[1].data_source.from_expression
        assert "2019-12-01" in configured.experiment.segments[1].data_source.from_expression

    def test_end_date_str(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            segments = ["my_cool_segment"]

            [segments.my_cool_segment]
            Data_Source = "my_cool_data_source"
            Select_Expression = "{{agg_any('1')}}"

            [segments.data_sources.my_cool_data_source]
            from_expression = "(SELECT 1 WHERE submission_date BETWEEN {{experiment.start_date_str}} AND {{experiment.end_date_str}})"
            """  # noqa
        )

        spec = AnalysisSpec.from_dict(toml.loads(conf))
        configured = spec.resolve(experiments[0], config_collection)

        assert len(configured.experiment.segments) == 1

        segment = configured.experiment.segments[0]
        assert isinstance(segment, Segment)

        assert segment.name == "my_cool_segment"

        assert "agg_any" not in segment.select_expression
        assert "1970" not in segment.data_source.from_expression
        assert "{{" not in segment.data_source.from_expression
        assert "2019-12-01" in segment.data_source.from_expression
        assert "2020-03-01" in segment.data_source.from_expression

        # Fails when `end_date=None`.
        with pytest.raises(NoEndDateException):
            spec = AnalysisSpec.from_dict(toml.loads(conf))
            configured = spec.resolve(experiments[8], config_collection)

        # Succeeds when `end_date=None` but it's not referenced; note
        # `last_enrollment_date_str` below.
        conf = dedent(
            """
            [experiment]
            segments = ["my_cool_segment"]

            [segments.my_cool_segment]
            Data_Source = "my_cool_data_source"
            Select_Expression = "{{agg_any('1')}}"

            [segments.data_sources.my_cool_data_source]
            from_expression = "(SELECT 1 WHERE submission_date BETWEEN {{experiment.start_date_str}} AND {{experiment.last_enrollment_date_str}})"
            """  # noqa
        )

        spec = AnalysisSpec.from_dict(toml.loads(conf))
        configured = spec.resolve(experiments[8], config_collection)

    def test_pre_treatment_config(self, experiments, config_collection):
        config_str = dedent(
            """
            [metrics]
            weekly = ["spam"]

            [metrics.spam]
            data_source = "main"
            select_expression = "1"

            [metrics.spam.statistics.bootstrap_mean]
            num_samples = 10
            pre_treatments = [
                {name = "remove_nulls"},
                {name = "log", base = 20.0},
                {name = "censor_highest_values", fraction = 0.9}
            ]
            """
        )

        spec = AnalysisSpec.from_dict(toml.loads(config_str))
        cfg = spec.resolve(experiments[0], config_collection)
        pre_treatments = [m for m in cfg.metrics[AnalysisPeriod.WEEK] if m.metric.name == "spam"][
            0
        ].pre_treatments

        assert len(pre_treatments) == 3
        assert pre_treatments[0].name == "remove_nulls"
        assert pre_treatments[1].name == "log"
        assert pre_treatments[2].name == "censor_highest_values"

        assert pre_treatments[1].args["base"] == 20.0
        assert pre_treatments[2].args["fraction"] == 0.9

    def test_pre_treatment_config_multiple_periods(self, experiments, config_collection):
        config_str = dedent(
            """
            [metrics]
            weekly = ["spam"]
            28_day = ["spam"]
            overall = ["spam"]

            [metrics.spam]
            data_source = "main"
            select_expression = "1"

            [metrics.spam.statistics.binomial]
            pre_treatments = ["remove_nulls"]
            """
        )

        spec = AnalysisSpec.from_dict(toml.loads(config_str))
        cfg = spec.resolve(experiments[0], config_collection)
        pre_treatments = [m for m in cfg.metrics[AnalysisPeriod.WEEK] if m.metric.name == "spam"][
            0
        ].pre_treatments

        assert len(pre_treatments) == 1
        assert pre_treatments[0].name == "remove_nulls"

        overall_pre_treatments = [
            m for m in cfg.metrics[AnalysisPeriod.OVERALL] if m.metric.name == "spam"
        ][0].pre_treatments

        assert len(overall_pre_treatments) == 1
        assert overall_pre_treatments[0].name == "remove_nulls"

    def test_preenrollment(self, experiments, config_collection):
        config_str = dedent(
            """
            [metrics]
            preenrollment_days28 = ["spam"]
            preenrollment_weekly = ["spam"]

            [metrics.spam]
            data_source = "main"
            select_expression = "1"

            [metrics.spam.statistics.binomial]
            """
        )

        spec = AnalysisSpec.from_dict(toml.loads(config_str))
        cfg = spec.resolve(experiments[0], config_collection)
        week_metrics = [
            m for m in cfg.metrics[AnalysisPeriod.PREENROLLMENT_WEEK] if m.metric.name == "spam"
        ]

        assert len(week_metrics) == 1
        assert week_metrics[0].metric.name == "spam"

        days28_metrics = [
            m for m in cfg.metrics[AnalysisPeriod.PREENROLLMENT_DAYS_28] if m.metric.name == "spam"
        ]

        assert len(days28_metrics) == 1
        assert days28_metrics[0].metric.name == "spam"

    def test_segment_resolution(self, experiments, config_collection):
        spec = AnalysisSpec()

        cfg = spec.resolve(experiments[9], config_collection)

        assert len(cfg.experiment.segments) == 1

        segment = cfg.experiment.segments[0]

        assert segment.name == "regular_users_v3"
        assert segment.data_source.name == "my_cool_data_source"
        expected_expression = """(SELECT 1 WHERE submission_date BETWEEN 2019-12-01
    AND 2019-12-08)"""
        assert expected_expression == segment.data_source.from_expression.strip()

    def test_segment_definition_and_experiment_segment(self, experiments, config_collection):
        config_str = dedent(
            """
            [experiment]
            segments = ["test_segment"]

            [segments.test_segment]
            Data_Source = "test_data_source"
            Select_Expression = "{{agg_any('1')}}"

            [segments.data_sources.test_data_source]
            from_expression = "(SELECT 1 WHERE submission_date BETWEEN {{experiment.start_date_str}} AND {{experiment.last_enrollment_date_str}})"
            """  # noqa
        )
        spec = AnalysisSpec.from_dict(toml.loads(config_str))
        cfg = spec.resolve(experiments[9], config_collection)

        assert len(cfg.experiment.segments) == 2

        custom_segment = [seg for seg in cfg.experiment.segments if seg.name == "test_segment"]

        assert len(custom_segment) == 1
        assert custom_segment[0].name == "test_segment"
        assert custom_segment[0].data_source.name == "test_data_source"
        expected_expression = (
            """(SELECT 1 WHERE submission_date BETWEEN 2019-12-01 AND 2019-12-08)"""
        )
        assert expected_expression == custom_segment[0].data_source.from_expression.strip()

        experiment_segments = [
            seg for seg in cfg.experiment.segments if seg.name == "regular_users_v3"
        ]

        assert len(experiment_segments) == 1
        assert experiment_segments[0].name == "regular_users_v3"
        assert experiment_segments[0].data_source.name == "my_cool_data_source"
        expected_expression = """(SELECT 1 WHERE submission_date BETWEEN 2019-12-01
    AND 2019-12-08)"""
        assert expected_expression == experiment_segments[0].data_source.from_expression.strip()

    def test_segment_duplication(self, experiments, config_collection):
        config_str = dedent(
            """
            [experiment]
            segments = ["regular_users_v3"]

            [segments.regular_users_v3]
            data_source = "my_cool_data_source"
            select_expression = "{{agg_any('1')}}"

            [segments.data_sources.my_cool_data_source]
            from_expression = '''
                (SELECT 1 WHERE submission_date BETWEEN {{experiment.start_date_str}}
                AND {{experiment.last_enrollment_date_str}})
            '''
            """
        )

        spec = AnalysisSpec.from_dict(toml.loads(config_str))
        cfg = spec.resolve(experiments[9], config_collection)

        assert len(cfg.experiment.segments) == 1
        assert cfg.experiment.segments[0].name == "regular_users_v3"
        assert cfg.experiment.segments[0].data_source.name == "my_cool_data_source"
        expected_expression = """(SELECT 1 WHERE submission_date BETWEEN 2019-12-01
    AND 2019-12-08)"""
        assert expected_expression == cfg.experiment.segments[0].data_source.from_expression.strip()


class TestExperimentConf:
    def test_bad_dates(self, experiments):
        conf = dedent(
            """
            [experiment]
            end_date = "Christmas"
            """
        )
        with pytest.raises(ClassValidationError):
            AnalysisSpec.from_dict(toml.loads(conf))

        conf = dedent(
            """
            [experiment]
            start_date = "My birthday"
            """
        )
        with pytest.raises(ClassValidationError):
            AnalysisSpec.from_dict(toml.loads(conf))

    def test_good_end_date(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            end_date = "2020-12-31"
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        live_experiment = [x for x in experiments if x.status == "Live"][0]
        cfg = spec.resolve(live_experiment, config_collection)
        assert cfg.experiment.end_date == dt.datetime(2020, 12, 31, tzinfo=pytz.utc)
        assert cfg.experiment.status == "Complete"

    def test_good_start_date(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            start_date = "2020-12-31"
            end_date = "2021-02-01"
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        cfg = spec.resolve(experiments[0], config_collection)
        assert cfg.experiment.start_date == dt.datetime(2020, 12, 31, tzinfo=pytz.utc)
        assert cfg.experiment.end_date == dt.datetime(2021, 2, 1, tzinfo=pytz.utc)

    def test_enrollment_end_date(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        cfg = spec.resolve(experiments[7], config_collection)
        assert cfg.experiment.enrollment_period == 3

    def test_enrollment_end_date_overwrite(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            enrollment_period = 8
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        cfg = spec.resolve(experiments[7], config_collection)
        assert cfg.experiment.enrollment_period == 8

    def test_private_experiment_no_dataset(self, experiments):
        conf = dedent(
            """
            [experiment]
            is_private = true
            """
        )
        with pytest.raises(ClassValidationError):
            AnalysisSpec.from_dict(toml.loads(conf))

    def test_private_experiment(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            is_private = true
            dataset_id = "test"
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        cfg = spec.resolve(experiments[7], config_collection)
        assert cfg.experiment.dataset_id == "test"

    def test_sample_size_defined_experiment(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            sample_size = 8
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        cfg = spec.resolve(experiments[7], config_collection)
        assert cfg.experiment.sample_size == 8

    def test_sample_size_none_experiment(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            enrollment_period = 7
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        cfg = spec.resolve(experiments[7], config_collection)
        assert cfg.experiment.sample_size is None

    def test_analysis_unit_default(self, experiments, config_collection):
        conf = dedent(
            """
            [experiment]
            enrollment_period = 7
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        cfg = spec.resolve(experiments[1], config_collection)
        assert cfg.experiment.randomization_unit is None
        assert cfg.experiment.analysis_unit == AnalysisUnit.CLIENT

    @pytest.mark.parametrize(
        "randomization_unit", [ru for ru in RandomizationUnit.__members__.values()]
    )
    def test_analysis_unit_configured(self, config_collection, randomization_unit):
        conf = dedent(
            """
            [experiment]
            enrollment_period = 7
            """
        )
        exp = Experiment(
            experimenter_slug="test_slug",
            type="pref",
            status="Complete",
            start_date=dt.datetime(2019, 12, 1, tzinfo=pytz.utc),
            end_date=dt.datetime(2020, 3, 1, tzinfo=pytz.utc),
            proposed_enrollment=7,
            branches=[Branch(slug="a", ratio=1), Branch(slug="b", ratio=1)],
            normandy_slug="normandy-test-slug",
            reference_branch="b",
            is_high_population=False,
            app_name="firefox_desktop",
            bucket_config=BucketConfig(
                randomization_unit=randomization_unit,
                namespace="testing",
                start=0,
                count=10,
                total=100,
            ),
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        cfg = spec.resolve(exp, config_collection)
        expected_randomization_unit = RandomizationUnit(randomization_unit)
        expected_analysis_unit = (
            AnalysisUnit.PROFILE_GROUP
            if expected_randomization_unit == RandomizationUnit.GROUP_ID
            else AnalysisUnit.CLIENT
        )
        assert cfg.experiment.randomization_unit == expected_randomization_unit
        assert cfg.experiment.analysis_unit == expected_analysis_unit

    @pytest.mark.parametrize("randomization_unit", [None, "invalid_id"])
    def test_analysis_unit_invalid(self, config_collection, randomization_unit):
        conf = dedent(
            """
            [experiment]
            enrollment_period = 7
            """
        )
        exp = Experiment(
            experimenter_slug="test_slug",
            type="pref",
            status="Complete",
            start_date=dt.datetime(2019, 12, 1, tzinfo=pytz.utc),
            end_date=dt.datetime(2020, 3, 1, tzinfo=pytz.utc),
            proposed_enrollment=7,
            branches=[Branch(slug="a", ratio=1), Branch(slug="b", ratio=1)],
            normandy_slug="normandy-test-slug",
            reference_branch="b",
            is_high_population=False,
            app_name="firefox_desktop",
            bucket_config=BucketConfig(
                randomization_unit=randomization_unit,
                namespace="testing",
                start=0,
                count=10,
                total=100,
            ),
        )
        spec = AnalysisSpec.from_dict(toml.loads(conf))
        cfg = spec.resolve(exp, config_collection)
        with pytest.raises(ValueError):
            cfg.experiment.randomization_unit
        with pytest.raises(ValueError):
            cfg.experiment.analysis_unit


class TestDefaultConfiguration:
    def test_descriptions_defined(self, experiments, config_collection):
        default_spec = AnalysisSpec.from_dict(toml.load(DEFAULT_METRICS_CONFIG))
        cfg = default_spec.resolve(experiments[0], config_collection)
        ever_ran = False

        for summaries in cfg.metrics.values():
            for _ in summaries:
                ever_ran = True
        assert ever_ran
