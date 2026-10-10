import datetime as dt
from pathlib import Path

import pytest
import toml

from metric_config_parser.aggregation import BucketedAggregation, Combine
from metric_config_parser.analysis import AnalysisSpec
from metric_config_parser.config import ConfigCollection, DefinitionConfig
from metric_config_parser.definition import DefinitionSpec
from metric_config_parser.function import FunctionsSpec
from metric_config_parser.metric import AnalysisPeriod, MetricDefinition
from metric_config_parser.util import converter

REPO_ROOT = Path(__file__).parents[4]
FUNCTIONS = FunctionsSpec.from_dict(toml.load(REPO_ROOT / "definitions" / "functions.toml"))

DATA_SOURCES = {
    "clients_daily": {"from_expression": "mozdata.telemetry.clients_daily"},
}


def parse_metric(**fields):
    return converter.structure(
        {"name": "m", "data_source": "clients_daily", **fields}, MetricDefinition
    )


def render(template):
    return ConfigCollection(functions=FUNCTIONS).get_env().from_string(template).render()


def resolve_weekly(config, metrics, experiment):
    definition = DefinitionConfig(
        slug="firefox_desktop",
        platform="firefox_desktop",
        spec=DefinitionSpec.from_dict({"metrics": metrics, "data_sources": DATA_SOURCES}),
        last_modified=dt.datetime.now(dt.UTC),
    )
    collection = ConfigCollection(definitions=[definition], functions=FUNCTIONS)
    return (
        AnalysisSpec.from_dict(config).resolve(experiment, collection).metrics[AnalysisPeriod.WEEK]
    )


class TestSelectExpression:
    @pytest.mark.parametrize(
        ("fields", "template", "rendered"),
        [
            ({"aggregation": "sum", "column": "a"}, '{{agg_sum("a")}}', "COALESCE(SUM(a), 0)"),
            ({"aggregation": "count", "column": "a"}, "COUNT(a)", "COUNT(a)"),
            (
                {
                    "aggregation": "count_where",
                    "where": [
                        {"column": "a", "op": ">", "value": 0},
                        {"column": "b", "op": ">", "value": 0},
                    ],
                },
                "COUNTIF(a > 0 AND b > 0)",
                "COUNTIF(a > 0 AND b > 0)",
            ),
            (
                {"aggregation": "any", "where": [{"column": "a"}]},
                '{{agg_any("a")}}',
                "COALESCE(LOGICAL_OR(a), FALSE)",
            ),
            (
                {"aggregation": "recency_within", "column": "a", "within_days": 3},
                "COALESCE(MIN(mozfun.bits28.days_since_seen(a)), 30) < 3",
                "COALESCE(MIN(mozfun.bits28.days_since_seen(a)), 30) < 3",
            ),
        ],
    )
    def test_aggregation(self, fields, template, rendered):
        metric = parse_metric(**fields)

        assert metric.generated_select_expression == template
        assert render(template) == rendered

    def test_select_expression_metric(self):
        metric = parse_metric(select_expression="SUM(a)")

        assert metric.generated_select_expression is None
        assert metric.bucketed_aggregation is None


class TestBucketedAggregation:
    @pytest.mark.parametrize(
        ("fields", "expected"),
        [
            (
                {"aggregation": "sum", "column": "a"},
                BucketedAggregation("SUM(a)", Combine.SUM, "0", "{combined}"),
            ),
            (
                {"aggregation": "count", "column": "a"},
                BucketedAggregation("COUNT(a)", Combine.SUM, "0", "{combined}"),
            ),
            (
                {
                    "aggregation": "count_where",
                    "where": [
                        {"column": "a", "op": ">", "value": 0},
                        {"column": "b", "op": ">", "value": 0},
                    ],
                },
                BucketedAggregation("COUNTIF(a > 0 AND b > 0)", Combine.SUM, "0", "{combined}"),
            ),
            (
                {"aggregation": "any", "where": [{"column": "a"}]},
                BucketedAggregation(
                    "COUNTIF(a)", Combine.SUM, "0", "CAST({combined} > 0 AS INT64)"
                ),
            ),
            (
                {"aggregation": "recency_within", "column": "a", "within_days": 3},
                BucketedAggregation(
                    "MIN(mozfun.bits28.days_since_seen(a))",
                    Combine.MIN,
                    "30",
                    "CAST({combined} < 3 AS INT64)",
                ),
            ),
        ],
    )
    def test_aggregation(self, fields, expected):
        assert parse_metric(**fields).bucketed_aggregation == expected

    def test_finalize_sql(self):
        bucketed = parse_metric(aggregation="any", column="a").bucketed_aggregation

        assert bucketed.finalize_sql("SUM(x)") == "CAST(SUM(x) > 0 AS INT64)"


class TestConditions:
    @pytest.mark.parametrize(
        ("clause", "predicate"),
        [
            ({"column": "a", "op": ">", "value": 0}, "a > 0"),
            ({"column": "a", "op": "!=", "value": -1.5}, "a != -1.5"),
            ({"column": "a", "op": "=", "value": True}, "a = TRUE"),
            ({"column": "a", "op": "IS NULL"}, "a IS NULL"),
            ({"column": "a", "op": "IS NOT NULL"}, "a IS NOT NULL"),
            ({"column": "a", "op": "=", "value": "release"}, "a = 'release'"),
            ({"column": "a", "op": "=", "value": "it's"}, "a = 'it\\'s'"),
            ({"column": "a", "op": "=", "value": 'a\\b "c"'}, "a = 'a\\\\b \"c\"'"),
            ({"column": "a", "op": "=", "value": "{{ x }}"}, "a = '\\x7b\\x7b x }}'"),
        ],
    )
    def test_operator(self, clause, predicate):
        metric = parse_metric(aggregation="any", where=[clause])

        assert render(metric.generated_select_expression) == (
            f"COALESCE(LOGICAL_OR({predicate}), FALSE)"
        )
        assert metric.bucketed_aggregation.bucket_aggregate == f"COUNTIF({predicate})"

    @pytest.mark.parametrize(
        ("value", "match"),
        [([1], "must be a number, string or boolean"), (float("nan"), "must be a finite number")],
    )
    def test_rejects_value(self, value, match):
        metric = parse_metric(
            aggregation="count_where", where=[{"column": "a", "op": "=", "value": value}]
        )

        with pytest.raises(ValueError, match=match):
            metric.generated_select_expression  # noqa: B018
        with pytest.raises(ValueError, match=match):
            metric.bucketed_aggregation  # noqa: B018

    def test_column_shorthand(self):
        shorthand = parse_metric(aggregation="count_where", column="a")
        where = parse_metric(aggregation="count_where", where=[{"column": "a"}])

        assert shorthand.generated_select_expression == where.generated_select_expression
        assert shorthand.bucketed_aggregation == where.bucketed_aggregation


class TestThresholdAndScale:
    @pytest.mark.parametrize(
        ("fields", "rendered", "finalize"),
        [
            (
                {"aggregation": "sum", "column": "a", "threshold": {"op": ">", "value": 0}},
                "COALESCE(SUM(a), 0) > 0",
                "CAST({combined} > 0 AS INT64)",
            ),
            (
                {"aggregation": "any", "column": "a", "threshold": {"op": "=", "value": 1}},
                "CAST(COALESCE(LOGICAL_OR(a), FALSE) AS INT64) = 1",
                "CAST(CAST({combined} > 0 AS INT64) = 1 AS INT64)",
            ),
        ],
    )
    def test_threshold(self, fields, rendered, finalize):
        metric = parse_metric(**fields)

        assert render(metric.generated_select_expression) == rendered
        assert metric.bucketed_aggregation.finalize == finalize

    @pytest.mark.parametrize(
        ("fields", "rendered", "finalize"),
        [
            (
                {"aggregation": "count_where", "column": "a", "scale": 1000},
                "COUNTIF(a) * 1000",
                "({combined}) * 1000",
            ),
            (
                {
                    "aggregation": "sum",
                    "column": "a",
                    "threshold": {"op": ">", "value": 0},
                    "scale": 0.5,
                },
                "CAST(COALESCE(SUM(a), 0) > 0 AS INT64) * 0.5",
                "(CAST({combined} > 0 AS INT64)) * 0.5",
            ),
        ],
    )
    def test_scale(self, fields, rendered, finalize):
        metric = parse_metric(**fields)

        assert render(metric.generated_select_expression) == rendered
        assert metric.bucketed_aggregation.finalize == finalize


class TestResolve:
    def test_definitions_metric_resolves_without_recursion(self, experiments):
        metrics = {
            "active_hours": {
                "data_source": "clients_daily",
                "aggregation": "sum",
                "column": "active_hours_sum",
                "statistics": {"bootstrap_mean": {}},
            }
        }

        [summary] = resolve_weekly(
            {"metrics": {"weekly": ["active_hours"]}}, metrics, experiments[0]
        )

        assert summary.metric.select_expression == "COALESCE(SUM(active_hours_sum), 0)"
        assert summary.metric.data_source.name == "clients_daily"
        assert summary.statistic.name == "bootstrap_mean"

    def test_experiment_config_metric(self, experiments):
        [summary] = resolve_weekly(
            {
                "metrics": {
                    "weekly": ["retained"],
                    "retained": {
                        "data_source": "clients_daily",
                        "aggregation": "sum",
                        "column": "pings_aggregated_by_this_row",
                        "threshold": {"op": ">", "value": 0},
                        "statistics": {"binomial": {}},
                    },
                }
            },
            {},
            experiments[0],
        )

        assert summary.metric.select_expression == (
            "COALESCE(SUM(pings_aggregated_by_this_row), 0) > 0"
        )
