import datetime as dt
from textwrap import dedent

import pytest
import pytz
import toml
from cattrs.errors import ClassValidationError

from metric_config_parser.analysis import AnalysisSpec
from metric_config_parser.experiment import Experiment
from metric_config_parser.metric import AnalysisPeriod
from metric_config_parser.outcome import OutcomeSpec


class TestOutcomes:
    def test_outcomes(self):
        config_str = dedent(
            """
            friendly_name = "Test outcome"
            description = "Outcome for testing"
            default_metrics = ["spam", "organic_search_count"]

            [metrics.spam]
            data_source = "main"
            select_expression = "1"

            [metrics.spam.statistics.bootstrap_mean]
            num_samples = 10
            pre_treatments = ["remove_nulls"]

            [metrics.organic_search_count.statistics.bootstrap_mean]

            [metrics.ad_clicks.statistics.bootstrap_mean]

            [data_sources.eggs]
            from_expression = "england.camelot"
            client_id_column = "client_info.client_id"
            """
        )

        outcome_spec = OutcomeSpec.from_dict(toml.loads(config_str))
        assert "spam" in outcome_spec.metrics
        assert "organic_search_count" in outcome_spec.metrics
        assert "ad_clicks" in outcome_spec.metrics
        assert "eggs" in outcome_spec.data_sources.definitions

        default_metrics = [m.name for m in outcome_spec.default_metrics]
        assert "spam" in default_metrics
        assert "organic_search_count" in default_metrics
        assert "ad_clicks" not in default_metrics

    def test_invalid_default_metrics(self):
        config_str = dedent(
            """
            friendly_name = "Test outcome"
            description = "Outcome for testing"
            default_metrics = ["spam"]

            [metrics.ad_clicks.statistics.bootstrap_mean]
            """
        )

        with pytest.raises(ValueError):
            OutcomeSpec.from_dict(toml.loads(config_str))

    def test_resolving_outcomes(self, experiments, config_collection):
        config_str = dedent(
            """
            [metrics]
            weekly = ["view_about_logins", "my_cool_metric"]
            daily = ["my_cool_metric"]

            [metrics.my_cool_metric]
            data_source = "main"
            select_expression = "{{agg_histogram_mean('payload.content.my_cool_histogram')}}"
            friendly_name = "Cool metric"
            description = "Cool cool cool 😎"
            bigger_is_better = false

            [metrics.my_cool_metric.statistics.bootstrap_mean]

            [metrics.view_about_logins.statistics.bootstrap_mean]
            """
        )

        spec = AnalysisSpec.from_dict(toml.loads(config_str))
        cfg = spec.resolve(experiments[5], config_collection)
        weekly_metrics = [s.metric.name for s in cfg.metrics[AnalysisPeriod.WEEK]]

        assert "view_about_logins" in weekly_metrics
        assert "my_cool_metric" in weekly_metrics

    def test_resolving_parameters(self, experiments, config_collection):
        config_str = dedent(
            """
            [parameters.id]
            value = "123"

            [metrics]
            weekly = ["view_about_logins", "my_cool_metric"]
            daily = ["my_cool_metric"]

            [metrics.my_cool_metric]
            data_source = "main"
            select_expression = "{{agg_histogram_mean('payload.content.my_cool_histogram')}}"
            friendly_name = "Cool metric"
            description = "Cool cool cool 😎"
            bigger_is_better = false

            [metrics.my_cool_metric.statistics.bootstrap_mean]

            [metrics.view_about_logins.statistics.bootstrap_mean]
            """
        )

        spec = AnalysisSpec.from_dict(toml.loads(config_str))
        cfg = spec.resolve(experiments[6], config_collection)
        weekly_metrics = [s.metric.name for s in cfg.metrics[AnalysisPeriod.WEEK]]

        assert len(weekly_metrics) == 3

        assert "id" in spec.parameters.definitions
        assert spec.parameters.definitions["id"].default == "700"
        assert spec.parameters.definitions["id"].value == "123"

        assert "view_about_logins" in weekly_metrics
        assert "my_cool_metric" in weekly_metrics

        outcome_metric = next(
            (
                m.metric
                for m in cfg.metrics[AnalysisPeriod.WEEK]
                if m.metric.name == "sample_id_count"
            )
        )
        assert outcome_metric.select_expression == "COUNTIF(sample_id = 123)"

    def test_resolving_parameters_distinct_by_branch(self, experiments, config_collection):
        config_str = dedent(
            """
            [parameters.id]
            distinct_by_branch = true

            value.branch_1 = "123"
            value.branch_2 = "456"

            default.branch_3 = "444"
            default.branch_1 = "444"

            [metrics]
            weekly = ["view_about_logins", "my_cool_metric"]
            daily = ["my_cool_metric"]

            [metrics.my_cool_metric]
            data_source = "main"
            select_expression = "{{agg_histogram_mean('payload.content.my_cool_histogram')}}"
            friendly_name = "Cool metric"
            description = "Cool cool cool 😎"
            bigger_is_better = false

            [metrics.my_cool_metric.statistics.bootstrap_mean]

            [metrics.view_about_logins.statistics.bootstrap_mean]
            """
        )

        spec = AnalysisSpec.from_dict(toml.loads(config_str))
        cfg = spec.resolve(experiments[6], config_collection)
        weekly_metrics = [s.metric.name for s in cfg.metrics[AnalysisPeriod.WEEK]]

        assert len(weekly_metrics) == 3

        assert "id" in spec.parameters.definitions
        assert spec.parameters.definitions["id"].value["branch_1"] == "123"
        assert spec.parameters.definitions["id"].value["branch_2"] == "456"
        assert spec.parameters.definitions["id"].value["branch_3"] == "444"

        assert "view_about_logins" in weekly_metrics
        assert "my_cool_metric" in weekly_metrics

        outcome_metric = next(
            (
                m.metric
                for m in cfg.metrics[AnalysisPeriod.WEEK]
                if m.metric.name == "sample_id_count"
            )
        )
        assert outcome_metric.select_expression == (
            """COUNTIF(sample_id = CASE e.branch """
            """WHEN "branch_3" THEN "444" WHEN "branch_1" """
            """THEN "123" WHEN "branch_2" THEN "456" END)"""
        )

    def test_resolving_parameters_default_value(self, experiments, config_collection):
        config_str = dedent(
            """
            [metrics]
            weekly = ["view_about_logins", "my_cool_metric"]
            daily = ["my_cool_metric"]

            [metrics.my_cool_metric]
            data_source = "main"
            select_expression = "{{agg_histogram_mean('payload.content.my_cool_histogram')}}"
            friendly_name = "Cool metric"
            description = "Cool cool cool 😎"
            bigger_is_better = false

            [metrics.my_cool_metric.statistics.bootstrap_mean]

            [metrics.view_about_logins.statistics.bootstrap_mean]
            """
        )

        spec = AnalysisSpec.from_dict(toml.loads(config_str))
        cfg = spec.resolve(experiments[6], config_collection)
        weekly_metrics = [s.metric.name for s in cfg.metrics[AnalysisPeriod.WEEK]]

        assert len(weekly_metrics) == 3

        assert "id" in spec.parameters.definitions
        assert spec.parameters.definitions["id"].value == "700"
        assert spec.parameters.definitions["id"].default == "700"

        assert "view_about_logins" in weekly_metrics
        assert "my_cool_metric" in weekly_metrics

        outcome_metric = next(
            (
                m.metric
                for m in cfg.metrics[AnalysisPeriod.WEEK]
                if m.metric.name == "sample_id_count"
            )
        )
        assert outcome_metric.select_expression == "COUNTIF(sample_id = 700)"

    def test_resolving_parameters_default_value_distinct_by_branch(
        self, experiments, config_collection
    ):
        config_str = dedent(
            """

            [parameters.id]
            # value.branch_1 = ""  # this will use default value from outcome
            value.branch_2 = 2  # this will use default value from outcome
            distinct_by_branch = true

            [metrics]
            weekly = ["view_about_logins", "my_cool_metric"]
            daily = ["my_cool_metric"]

            [metrics.my_cool_metric]
            data_source = "main"
            select_expression = "{{agg_histogram_mean('payload.content.my_cool_histogram')}}"
            friendly_name = "Cool metric"
            description = "Cool cool cool 😎"
            bigger_is_better = false

            [metrics.my_cool_metric.statistics.bootstrap_mean]

            [metrics.view_about_logins.statistics.bootstrap_mean]
            """
        )

        spec = AnalysisSpec.from_dict(toml.loads(config_str))
        cfg = spec.resolve(experiments[7], config_collection)
        weekly_metrics = [s.metric.name for s in cfg.metrics[AnalysisPeriod.WEEK]]

        assert len(weekly_metrics) == 3

        assert "id" in spec.parameters.definitions
        assert isinstance(spec.parameters.definitions["id"].default, dict)

        assert len(spec.parameters.definitions["id"].default) == 1
        assert "branch_2" not in spec.parameters.definitions["id"].default
        assert spec.parameters.definitions["id"].default["branch_1"] == 1

        assert spec.parameters.definitions["id"].value["branch_1"] == 1
        assert spec.parameters.definitions["id"].value["branch_2"] == 2

        assert "view_about_logins" in weekly_metrics
        assert "my_cool_metric" in weekly_metrics

        outcome_metric = next(
            (
                m.metric
                for m in cfg.metrics[AnalysisPeriod.WEEK]
                if m.metric.name == "sample_id_count"
            )
        )
        assert outcome_metric.select_expression == (
            """COUNTIF(sample_id = CASE e.branch """
            """WHEN "branch_1" THEN "1" WHEN "branch_2" THEN "2" END)"""
        )

    def test_resolving_parameters_distinct_by_branch_missing_branch_name_raises(self):
        """
        If distinct_by_branch is set to `true`
        `id.branch_name` value should be specified
        otherwise we raise an exception
        """

        config_str = dedent(
            """
            [parameters.id]
            id.value = "1234"
            value = "567"
            distinct_by_branch = true

            [metrics]
            weekly = ["view_about_logins", "my_cool_metric"]
            daily = ["my_cool_metric"]

            [metrics.my_cool_metric]
            data_source = "main"
            select_expression = "{{agg_histogram_mean('payload.content.my_cool_histogram')}}"
            friendly_name = "Cool metric"
            description = "Cool cool cool 😎"
            bigger_is_better = false

            [metrics.my_cool_metric.statistics.bootstrap_mean]

            [metrics.view_about_logins.statistics.bootstrap_mean]
            """
        )

        with pytest.raises(ClassValidationError):
            AnalysisSpec.from_dict(toml.loads(config_str))

    def test_unsupported_platform_outcomes(self, config_collection):
        spec = AnalysisSpec.from_dict(toml.loads(""))
        experiment = Experiment(
            experimenter_slug="test_slug",
            type="pref",
            status="Live",
            start_date=dt.datetime(2019, 12, 1, tzinfo=pytz.utc),
            end_date=dt.datetime(2020, 3, 1, tzinfo=pytz.utc),
            proposed_enrollment=7,
            branches=[],
            normandy_slug="normandy-test-slug",
            reference_branch=None,
            is_high_population=True,
            outcomes=["performance"],
            app_name="fenix",
        )

        with pytest.raises(ValueError):
            spec.resolve(experiment, config_collection)
