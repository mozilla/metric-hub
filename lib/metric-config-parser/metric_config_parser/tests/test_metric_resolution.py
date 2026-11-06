import datetime as dt
from textwrap import dedent

import pytest
import pytz
from git import Repo
from mozilla_nimbus_schemas.jetstream import AnalysisBasis

from metric_config_parser import AnalysisUnit
from metric_config_parser.analysis import AnalysisSpec
from metric_config_parser.config import NIMBUS_DEFINITIONS_DIR, ConfigCollection
from metric_config_parser.experiment import Branch, Experiment
from metric_config_parser.metric import AnalysisPeriod

APP_NAME = "firefox_desktop"
EXPERIMENT_SLUG = "test-experiment"
OUTCOME_SLUG = "test_outcome"
APP_FILE = f"{APP_NAME}.toml"

BASE_DEFINITIONS = """
[metrics.retained]
select_expression = "base_retained"
data_source = "base_source"
friendly_name = "Retained"
description = "Retained in the base definitions"

[metrics.retained_new_users]
select_expression = "base_retained_new_users"
data_source = "base_source"
friendly_name = "Retained new users"

[metrics.searches]
select_expression = "base_searches"
data_source = "base_source"
friendly_name = "Searches"

[data_sources.base_source]
from_expression = "base_table"
"""

OVERLAY_DEFINITIONS = """
[metrics.retained]
select_expression = "overlay_retained"
data_source = "overlay_source"
friendly_name = "Overlay retained"

[metrics.retained.statistics.bootstrap_mean]

[metrics.searches.statistics.binomial]

[metrics.overlay_only]
select_expression = "overlay_only"
data_source = "overlay_source"

[metrics.overlay_only.statistics.bootstrap_mean]

[data_sources.overlay_source]
from_expression = "overlay_table"
"""

DEFAULTS_SEARCHES_SQL = """
[metrics]
weekly = ["searches"]

[metrics.searches]
select_expression = "defaults_searches"
data_source = "defaults_source"

[metrics.searches.statistics.deciles]

[data_sources.defaults_source]
from_expression = "defaults_table"
"""

OUTCOME_HEADER = """
friendly_name = "Test outcome"
description = "Outcome for testing"
"""

NIMBUS_DEFINITIONS = """
[metrics.days_of_use]
data_source = "base_source"
aggregation = "count"
column = "submission_date"
"""


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content))


def init_repo(root):
    r = Repo.init(root)
    r.config_writer().set_value("user", "name", "test").release()
    r.config_writer().set_value("user", "email", "test@example.com").release()
    r.config_writer().set_value("commit", "gpgsign", "false").release()
    r.git.add(".")
    r.git.commit("-m", "commit")
    return root


def load_layers(
    root,
    overlay=OVERLAY_DEFINITIONS,
    defaults=None,
    outcome=None,
    experiment="",
    nimbus=None,
):
    write(root / "definitions" / APP_FILE, BASE_DEFINITIONS)
    if nimbus is not None:
        write(root / NIMBUS_DEFINITIONS_DIR / APP_FILE, nimbus)
    jetstream = root / "jetstream"
    if overlay is not None:
        write(jetstream / "definitions" / APP_FILE, overlay)
    if defaults is not None:
        write(jetstream / "defaults" / APP_FILE, defaults)
    if outcome is not None:
        write(jetstream / "outcomes" / APP_NAME / f"{OUTCOME_SLUG}.toml", outcome)
    write(jetstream / f"{EXPERIMENT_SLUG}.toml", experiment)
    init_repo(root)
    return ConfigCollection.from_github_repos([str(root), str(jetstream)])


def make_experiment(outcomes=()):
    return Experiment(
        experimenter_slug=EXPERIMENT_SLUG,
        normandy_slug=EXPERIMENT_SLUG,
        type="v6",
        status="Live",
        start_date=dt.datetime(2026, 1, 1, tzinfo=pytz.utc),
        end_date=dt.datetime(2026, 2, 1, tzinfo=pytz.utc),
        proposed_enrollment=7,
        branches=[Branch(slug="control", ratio=1), Branch(slug="treatment", ratio=1)],
        reference_branch="control",
        is_high_population=False,
        app_name=APP_NAME,
        outcomes=list(outcomes),
    )


def resolve(configs, outcomes=()):
    experiment = make_experiment(outcomes)
    spec = AnalysisSpec.default_for_experiment(experiment, configs)
    spec.merge(configs.spec_for_experiment(EXPERIMENT_SLUG))
    return spec.resolve(experiment, configs)


def weekly(cfg, name):
    return {
        summary.statistic.name: summary
        for summary in cfg.metrics[AnalysisPeriod.WEEK]
        if summary.metric.name == name
    }


def only_metric(summaries):
    metrics = [summary.metric for summary in summaries.values()]
    assert all(metric == metrics[0] for metric in metrics)
    return metrics[0]


def bootstrap_mean(num_samples):
    return f"[metrics.retained.statistics.bootstrap_mean]\nnum_samples = {num_samples}"


class TestToolingOverlay:
    def test_overlay_overrides_sql_and_data_source_field_by_field(self, tmp_path):
        configs = load_layers(tmp_path, experiment='[metrics]\nweekly = ["retained"]')

        summaries = weekly(resolve(configs), "retained")

        assert set(summaries) == {"bootstrap_mean"}
        metric = only_metric(summaries)
        assert metric.select_expression == "overlay_retained"
        assert metric.data_source.name == "overlay_source"
        assert metric.data_source.from_expression == "overlay_table"
        assert metric.friendly_name == "Overlay retained"
        assert metric.description == "Retained in the base definitions"

    def test_overlay_statistics_only_keeps_base_definition(self, tmp_path):
        configs = load_layers(tmp_path, experiment='[metrics]\nweekly = ["searches"]')

        summaries = weekly(resolve(configs), "searches")

        assert set(summaries) == {"binomial"}
        metric = only_metric(summaries)
        assert metric.select_expression == "base_searches"
        assert metric.data_source.name == "base_source"
        assert metric.friendly_name == "Searches"

    def test_overlay_adds_new_metric(self, tmp_path):
        configs = load_layers(tmp_path, experiment='[metrics]\nweekly = ["overlay_only"]')

        summaries = weekly(resolve(configs), "overlay_only")

        assert set(summaries) == {"bootstrap_mean"}
        metric = only_metric(summaries)
        assert metric.select_expression == "overlay_only"
        assert metric.data_source.name == "overlay_source"

    def test_wildcard_overlay_applies_to_matching_metrics_only(self, tmp_path):
        overlay = """
        [metrics.'retained*']
        category = "retention"

        [metrics.'retained*'.statistics.binomial]

        [metrics.searches.statistics.deciles]
        """
        configs = load_layers(
            tmp_path, overlay=overlay, experiment='[metrics]\nweekly = ["searches"]'
        )

        for name in ["retained", "retained_new_users"]:
            definition = configs.get_metric_definition(name, APP_NAME)
            assert definition.statistics == {"binomial": {}}
            assert definition.category == "retention"
            assert definition.select_expression == f"base_{name}"
            assert definition.data_source.name == "base_source"
        assert configs.get_metric_definition("retained*", APP_NAME) is None

        searches = weekly(resolve(configs), "searches")
        assert set(searches) == {"deciles"}
        metric = only_metric(searches)
        assert metric.select_expression == "base_searches"
        assert metric.category is None

    @pytest.mark.parametrize(
        ("order", "expected_select_expression"),
        [
            (["base", "first", "second"], "second_retained"),
            (["base", "second", "first"], "first_retained"),
            (["first", "base"], "base_retained"),
        ],
    )
    def test_later_repo_overrides_earlier_repo(self, tmp_path, order, expected_select_expression):
        repo_definitions = {
            "base": BASE_DEFINITIONS,
            "first": """
            [metrics.retained]
            select_expression = "first_retained"

            [metrics.retained.statistics.bootstrap_mean]
            """,
            "second": """
            [metrics.retained]
            select_expression = "second_retained"
            """,
        }
        for name in order:
            write(tmp_path / name / "definitions" / APP_FILE, repo_definitions[name])
            init_repo(tmp_path / name)
        configs = ConfigCollection.from_github_repos([str(tmp_path / name) for name in order])

        spec = AnalysisSpec.from_dict({"metrics": {"weekly": ["retained"]}})
        summaries = weekly(spec.resolve(make_experiment(), configs), "retained")

        assert set(summaries) == {"bootstrap_mean"}
        metric = only_metric(summaries)
        assert metric.select_expression == expected_select_expression
        assert metric.data_source.name == "base_source"
        assert metric.friendly_name == "Retained"


class TestPlatformDefaults:
    def test_defaults_listed_metric_resolves_from_overlaid_base(self, tmp_path):
        configs = load_layers(tmp_path, defaults='[metrics]\nweekly = ["searches"]')

        summaries = weekly(resolve(configs), "searches")

        assert set(summaries) == {"binomial"}
        assert only_metric(summaries).select_expression == "base_searches"

    def test_defaults_statistics_only_keeps_overlaid_definition(self, tmp_path):
        defaults = """
        [metrics]
        weekly = ["retained"]

        [metrics.retained]
        analysis_bases = ["exposures"]

        [metrics.retained.statistics.deciles]
        """
        configs = load_layers(tmp_path, defaults=defaults)

        summaries = weekly(resolve(configs), "retained")

        assert set(summaries) == {"deciles"}
        metric = only_metric(summaries)
        assert metric.select_expression == "overlay_retained"
        assert metric.data_source.name == "overlay_source"
        assert metric.friendly_name == "Overlay retained"
        assert metric.analysis_bases == [AnalysisBasis.EXPOSURES]

    def test_defaults_sql_override_replaces_base_definition(self, tmp_path):
        configs = load_layers(tmp_path, defaults=DEFAULTS_SEARCHES_SQL)

        summaries = weekly(resolve(configs), "searches")

        assert set(summaries) == {"deciles"}
        metric = only_metric(summaries)
        assert metric.select_expression == "defaults_searches"
        assert metric.data_source.name == "defaults_source"
        assert metric.data_source.from_expression == "defaults_table"
        assert metric.friendly_name is None


class TestOutcome:
    def test_outcome_statistics_on_base_metric(self, tmp_path):
        outcome = f"{OUTCOME_HEADER}\n[metrics.retained.statistics.deciles]"
        configs = load_layers(tmp_path, outcome=outcome)

        cfg = resolve(configs, outcomes=[OUTCOME_SLUG])

        summaries = weekly(cfg, "retained")
        assert set(summaries) == {"deciles"}
        metric = only_metric(summaries)
        assert metric.select_expression == "overlay_retained"
        assert metric.data_source.name == "overlay_source"
        assert {s.metric.name for s in cfg.metrics[AnalysisPeriod.OVERALL]} == {"retained"}

    def test_outcome_sql_override_of_base_metric(self, tmp_path):
        searches = """
        [metrics.searches]
        select_expression = "outcome_searches"
        data_source = "base_source"

        [metrics.searches.statistics.deciles]
        """
        outcome = f"{OUTCOME_HEADER}\n{dedent(searches)}"
        configs = load_layers(tmp_path, outcome=outcome)

        summaries = weekly(resolve(configs, outcomes=[OUTCOME_SLUG]), "searches")

        assert set(summaries) == {"deciles"}
        metric = only_metric(summaries)
        assert metric.select_expression == "outcome_searches"
        assert metric.friendly_name is None


class TestExperimentConfig:
    def test_experiment_sql_override_of_overlaid_metric(self, tmp_path):
        experiment = """
        [metrics]
        weekly = ["retained"]

        [metrics.retained]
        select_expression = "experiment_retained"
        data_source = "base_source"

        [metrics.retained.statistics.binomial]
        """
        configs = load_layers(tmp_path, experiment=experiment)

        summaries = weekly(resolve(configs), "retained")

        assert set(summaries) == {"binomial"}
        metric = only_metric(summaries)
        assert metric.select_expression == "experiment_retained"
        assert metric.data_source.name == "base_source"
        assert metric.friendly_name is None

    def test_experiment_partial_override_of_overlaid_metric(self, tmp_path):
        experiment = """
        [metrics]
        weekly = ["retained"]

        [metrics.retained]
        analysis_bases = ["exposures"]
        analysis_units = ["client_id"]

        [metrics.retained.statistics.binomial]
        """
        configs = load_layers(tmp_path, experiment=experiment)

        summaries = weekly(resolve(configs), "retained")

        assert set(summaries) == {"binomial"}
        metric = only_metric(summaries)
        assert metric.select_expression == "overlay_retained"
        assert metric.data_source.name == "overlay_source"
        assert metric.friendly_name == "Overlay retained"
        assert metric.description == "Retained in the base definitions"
        assert metric.analysis_bases == [AnalysisBasis.EXPOSURES]
        assert metric.analysis_units == [AnalysisUnit.CLIENT]

        shared = configs.get_metric_definition("retained", APP_NAME)
        assert shared.statistics == {"bootstrap_mean": {}}
        assert shared.analysis_bases is None
        assert shared.analysis_units is None

    def test_experiment_sql_override_of_defaults_sql(self, tmp_path):
        experiment = """
        [metrics.searches]
        select_expression = "experiment_searches"

        [metrics.searches.statistics.binomial]
        """
        configs = load_layers(tmp_path, defaults=DEFAULTS_SEARCHES_SQL, experiment=experiment)

        summaries = weekly(resolve(configs), "searches")

        assert set(summaries) == {"binomial"}
        metric = only_metric(summaries)
        assert metric.select_expression == "experiment_searches"
        assert metric.data_source.name == "defaults_source"

    def test_experiment_partial_override_of_defaults_sql(self, tmp_path):
        experiment = "[metrics.searches.statistics.binomial]"
        configs = load_layers(tmp_path, defaults=DEFAULTS_SEARCHES_SQL, experiment=experiment)

        summaries = weekly(resolve(configs), "searches")

        assert set(summaries) == {"binomial"}
        metric = only_metric(summaries)
        assert metric.select_expression == "defaults_searches"
        assert metric.data_source.name == "defaults_source"


class TestLayerPrecedence:
    @pytest.mark.parametrize(
        ("layers", "expected_num_samples"),
        [
            pytest.param(set(), 1, id="overlay"),
            pytest.param({"outcome"}, 2, id="outcome_over_overlay"),
            pytest.param({"defaults"}, 3, id="defaults_over_overlay"),
            pytest.param({"outcome", "defaults"}, 3, id="defaults_over_outcome"),
            pytest.param({"experiment"}, 4, id="experiment_over_overlay"),
            pytest.param({"outcome", "defaults", "experiment"}, 4, id="experiment_over_all"),
        ],
    )
    def test_statistics_precedence(self, tmp_path, layers, expected_num_samples):
        listing = '[metrics]\nweekly = ["retained"]'
        experiment = listing
        if "experiment" in layers:
            experiment = f"{listing}\n{bootstrap_mean(4)}"
        configs = load_layers(
            tmp_path,
            overlay=bootstrap_mean(1),
            outcome=f"{OUTCOME_HEADER}\n{bootstrap_mean(2)}" if "outcome" in layers else None,
            defaults=f"{listing}\n{bootstrap_mean(3)}" if "defaults" in layers else None,
            experiment=experiment,
        )
        outcomes = [OUTCOME_SLUG] if "outcome" in layers else []

        summaries = weekly(resolve(configs, outcomes=outcomes), "retained")

        assert set(summaries) == {"bootstrap_mean"}
        assert summaries["bootstrap_mean"].statistic.params == {"num_samples": expected_num_samples}
        assert only_metric(summaries).select_expression == "base_retained"

    @pytest.mark.parametrize(
        ("layers", "expected_select_expression"),
        [
            pytest.param(set(), "overlay_retained", id="overlay"),
            pytest.param({"outcome"}, "outcome_retained", id="outcome_over_overlay"),
            pytest.param({"defaults"}, "defaults_retained", id="defaults_over_overlay"),
            pytest.param({"outcome", "defaults"}, "defaults_retained", id="defaults_over_outcome"),
            pytest.param({"experiment"}, "experiment_retained", id="experiment_over_overlay"),
            pytest.param(
                {"outcome", "defaults", "experiment"},
                "experiment_retained",
                id="experiment_over_all",
            ),
        ],
    )
    def test_select_expression_precedence(self, tmp_path, layers, expected_select_expression):
        listing = '[metrics]\nweekly = ["retained"]'

        def definition(layer):
            return dedent(
                f"""
                [metrics.retained]
                select_expression = "{layer}_retained"
                data_source = "base_source"

                [metrics.retained.statistics.bootstrap_mean]
                """
            )

        experiment = listing
        if "experiment" in layers:
            experiment = f"{listing}\n{definition('experiment')}"
        configs = load_layers(
            tmp_path,
            outcome=f"{OUTCOME_HEADER}\n{definition('outcome')}" if "outcome" in layers else None,
            defaults=f"{listing}\n{definition('defaults')}" if "defaults" in layers else None,
            experiment=experiment,
        )
        outcomes = [OUTCOME_SLUG] if "outcome" in layers else []

        summaries = weekly(resolve(configs, outcomes=outcomes), "retained")

        assert set(summaries) == {"bootstrap_mean"}
        assert only_metric(summaries).select_expression == expected_select_expression


class TestCrossLayer:
    def test_depends_on_upstream_metrics_from_different_layers(self, tmp_path):
        experiment = """
        [metrics]
        weekly = ["retained_per_search"]

        [metrics.retained_per_search]
        depends_on = ["retained", "searches"]

        [metrics.retained_per_search.statistics.population_ratio]
        numerator = "retained"
        denominator = "searches"
        """
        configs = load_layers(tmp_path, defaults=DEFAULTS_SEARCHES_SQL, experiment=experiment)

        summaries = weekly(resolve(configs), "retained_per_search")

        metric = only_metric(summaries)
        upstream = {
            (s.metric.name, s.metric.select_expression, s.statistic.name) for s in metric.depends_on
        }
        assert upstream == {
            ("retained", "overlay_retained", "bootstrap_mean"),
            ("searches", "defaults_searches", "deciles"),
        }

    def test_nimbus_definitions_for_app_leave_other_metrics_unchanged(self, tmp_path):
        experiment = """
        [metrics]
        weekly = ["retained", "searches", "overlay_only"]

        [metrics.retained]
        analysis_bases = ["exposures"]

        [metrics.retained.statistics.binomial]
        """
        without_nimbus = load_layers(
            tmp_path / "without_nimbus", defaults=DEFAULTS_SEARCHES_SQL, experiment=experiment
        )
        with_nimbus = load_layers(
            tmp_path / "with_nimbus",
            defaults=DEFAULTS_SEARCHES_SQL,
            experiment=experiment,
            nimbus=NIMBUS_DEFINITIONS,
        )

        assert [c.slug for c in with_nimbus.nimbus_configs] == [APP_NAME]
        assert with_nimbus.get_nimbus_metric_definition("retained", APP_NAME) is None
        cfg = resolve(with_nimbus)
        assert cfg.metrics == resolve(without_nimbus).metrics
        assert only_metric(weekly(cfg, "retained")).select_expression == "overlay_retained"
        assert only_metric(weekly(cfg, "searches")).select_expression == "defaults_searches"
