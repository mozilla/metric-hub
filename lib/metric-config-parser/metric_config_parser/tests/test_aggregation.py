import datetime as dt
from pathlib import Path

import pytest
import toml
from cattrs.errors import ClassValidationError

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

        assert metric.select_expression_from_aggregation == template
        assert render(template) == rendered

    def test_select_expression_metric(self):
        metric = parse_metric(select_expression="SUM(a)")

        assert metric.select_expression_from_aggregation is None
        assert metric.bucketed_aggregation is None


class TestBucketedAggregation:
    @pytest.mark.parametrize(
        ("fields", "expected"),
        [
            (
                {"aggregation": "sum", "column": "a"},
                BucketedAggregation("COALESCE(SUM(a), 0)", Combine.SUM, "0", "{combined}"),
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
                    "COALESCE(MIN(mozfun.bits28.days_since_seen(a)), 30)",
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

        assert render(metric.select_expression_from_aggregation) == (
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
            metric.select_expression_from_aggregation  # noqa: B018
        with pytest.raises(ValueError, match=match):
            metric.bucketed_aggregation  # noqa: B018

    def test_column_shorthand(self):
        shorthand = parse_metric(aggregation="count_where", column="a")
        where = parse_metric(aggregation="count_where", where=[{"column": "a"}])

        assert (
            shorthand.select_expression_from_aggregation == where.select_expression_from_aggregation
        )
        assert shorthand.bucketed_aggregation == where.bucketed_aggregation


class TestDottedColumn:
    def test_sum_with_dotted_column(self):
        metric = parse_metric(aggregation="sum", column="metrics.counter.example_counter")

        assert metric.select_expression_from_aggregation == (
            '{{agg_sum("metrics.counter.example_counter")}}'
        )
        assert render(metric.select_expression_from_aggregation) == (
            "COALESCE(SUM(metrics.counter.example_counter), 0)"
        )
        assert metric.bucketed_aggregation == BucketedAggregation(
            "COALESCE(SUM(metrics.counter.example_counter), 0)",
            Combine.SUM,
            "0",
            "{combined}",
        )

    def test_condition_with_dotted_column(self):
        metric = parse_metric(
            aggregation="count_where",
            where=[{"column": "payload.processes.parent.scalars.a", "op": ">", "value": 0}],
        )

        assert metric.select_expression_from_aggregation == (
            "COUNTIF(payload.processes.parent.scalars.a > 0)"
        )
        assert metric.bucketed_aggregation.bucket_aggregate == (
            "COUNTIF(payload.processes.parent.scalars.a > 0)"
        )

    def test_column_shorthand_with_dotted_column(self):
        shorthand = parse_metric(aggregation="any", column="metrics.boolean.flag")
        where = parse_metric(aggregation="any", where=[{"column": "metrics.boolean.flag"}])

        assert (
            shorthand.select_expression_from_aggregation == where.select_expression_from_aggregation
        )
        assert shorthand.bucketed_aggregation == where.bucketed_aggregation

    @pytest.mark.parametrize(
        "column",
        ["COALESCE(a, 0)", "1a", "a.1b", "a..b", "a.", ".a", "a > 0", "a.b.", "a b"],
    )
    def test_rejects_non_identifier_columns(self, column):
        with pytest.raises(ClassValidationError) as exc_info:
            parse_metric(aggregation="sum", column=column)

        assert exc_info.group_contains(ValueError, match="must be a plain column name")


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

        assert render(metric.select_expression_from_aggregation) == rendered
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

        assert render(metric.select_expression_from_aggregation) == rendered
        assert metric.bucketed_aggregation.finalize == finalize


class TestCoalesce:
    @pytest.mark.parametrize(
        ("fields", "template", "bucketed"),
        [
            (
                {"aggregation": "sum", "column": "a"},
                '{{agg_sum("a")}}',
                BucketedAggregation("COALESCE(SUM(a), 0)", Combine.SUM, "0", "{combined}"),
            ),
            (
                {"aggregation": "sum", "column": "a", "coalesce": "none"},
                "SUM(a)",
                BucketedAggregation("SUM(a)", Combine.SUM, "NULL", "{combined}"),
            ),
            (
                {"aggregation": "count_where", "column": "a"},
                "COUNTIF(a)",
                BucketedAggregation("COUNTIF(a)", Combine.SUM, "0", "{combined}"),
            ),
            (
                {"aggregation": "count_where", "column": "a", "coalesce": "aggregate"},
                "COALESCE(COUNTIF(a), 0)",
                BucketedAggregation("COALESCE(COUNTIF(a), 0)", Combine.SUM, "0", "{combined}"),
            ),
            (
                {"aggregation": "any", "column": "a", "coalesce": "none"},
                "LOGICAL_OR(a)",
                BucketedAggregation(
                    "COUNTIF(a)", Combine.SUM, "0", "CAST({combined} > 0 AS INT64)"
                ),
            ),
        ],
    )
    def test_coalesce_mode(self, fields, template, bucketed):
        metric = parse_metric(**fields)

        assert metric.select_expression_from_aggregation == template
        assert metric.bucketed_aggregation == bucketed

    def test_coalesce_result_wraps_final_expression(self):
        metric = parse_metric(
            aggregation="sum", column="a", coalesce="result", threshold={"op": ">", "value": 0}
        )

        assert render(metric.select_expression_from_aggregation) == "COALESCE(SUM(a) > 0, FALSE)"
        assert metric.bucketed_aggregation.bucket_aggregate == "SUM(a)"
        assert metric.bucketed_aggregation.no_rows == "NULL"

    def test_coalesce_result_on_any_defaults_to_false(self):
        metric = parse_metric(aggregation="any", column="a", coalesce="result")

        assert render(metric.select_expression_from_aggregation) == (
            "COALESCE(LOGICAL_OR(a), FALSE)"
        )

    @pytest.mark.parametrize("aggregation", ["count", "recency_within"])
    def test_rejects_coalesce_on_other_aggregations(self, aggregation):
        fields = {"aggregation": aggregation, "column": "a", "coalesce": "none"}
        if aggregation == "recency_within":
            fields["within_days"] = 3
        with pytest.raises(ClassValidationError) as exc_info:
            parse_metric(**fields)
        assert exc_info.group_contains(ValueError, match="coalesce is only valid for")

    def test_rejects_coalesce_without_aggregation(self):
        with pytest.raises(ClassValidationError) as exc_info:
            parse_metric(coalesce="none")
        assert exc_info.group_contains(ValueError, match="require aggregation")


class TestCastAsInt:
    def test_any_with_no_threshold(self):
        metric = parse_metric(aggregation="any", column="a", cast_as_int=True)

        assert render(metric.select_expression_from_aggregation) == (
            "CAST(COALESCE(LOGICAL_OR(a), FALSE) AS INT64)"
        )

    def test_recency_within(self):
        metric = parse_metric(
            aggregation="recency_within", column="a", within_days=3, cast_as_int=True
        )

        assert metric.select_expression_from_aggregation == (
            "CAST(COALESCE(MIN(mozfun.bits28.days_since_seen(a)), 30) < 3 AS INT64)"
        )


class TestRecencyEncoding:
    def test_bits28_is_the_default(self):
        default = parse_metric(aggregation="recency_within", column="a", within_days=3)
        explicit = parse_metric(
            aggregation="recency_within", column="a", within_days=3, encoding="bits28"
        )

        assert (
            default.select_expression_from_aggregation
            == explicit.select_expression_from_aggregation
        )
        assert default.bucketed_aggregation == explicit.bucketed_aggregation

    def test_days_encoding(self):
        metric = parse_metric(
            aggregation="recency_within",
            column="days_since_desktop_active",
            encoding="days",
            within_days=3,
        )

        assert metric.select_expression_from_aggregation == (
            "COALESCE(MIN(days_since_desktop_active), 30) < 3"
        )
        assert metric.bucketed_aggregation == BucketedAggregation(
            "COALESCE(MIN(days_since_desktop_active), 30)",
            Combine.MIN,
            "30",
            "CAST({combined} < 3 AS INT64)",
        )


class TestSingleBucketCollapse:
    """Over exactly one bucket, combine(bucket_aggregate) is the identity, so the
    window's combined value is bucket_aggregate itself. Where neither side casts a
    boolean to INT64 (no threshold, and the aggregation is not any/recency_within),
    that text must equal the Jetstream expression exactly. Where one side does
    (any, recency_within, or any aggregation with a threshold or cast_as_int),
    Highwind always returns INT64 and Jetstream does not unless something follows
    the boolean, so the two compute the same value without being the same text;
    that half of this test documents the known gap instead of asserting a false
    equality.
    """

    @pytest.mark.parametrize(
        "fields",
        [
            {"aggregation": "sum", "column": "a"},
            {"aggregation": "sum", "column": "a", "coalesce": "none"},
            {"aggregation": "count", "column": "a"},
            {"aggregation": "count_where", "column": "a"},
            {"aggregation": "count_where", "column": "a", "coalesce": "aggregate"},
        ],
    )
    def test_collapses_to_jetstream_text(self, fields):
        metric = parse_metric(**fields)
        bucketed = metric.bucketed_aggregation

        collapsed = bucketed.finalize_sql(bucketed.bucket_aggregate)

        assert render(collapsed) == render(metric.select_expression_from_aggregation)

    @pytest.mark.parametrize(
        "fields",
        [
            {"aggregation": "any", "column": "a"},
            {"aggregation": "any", "column": "a", "coalesce": "none"},
            {"aggregation": "recency_within", "column": "a", "within_days": 3},
            {"aggregation": "sum", "column": "a", "threshold": {"op": ">", "value": 0}},
            {
                "aggregation": "recency_within",
                "column": "days_since_desktop_active",
                "encoding": "days",
                "within_days": 3,
            },
            {"aggregation": "any", "column": "a", "cast_as_int": True},
        ],
    )
    def test_collapses_to_the_same_value_not_text(self, fields):
        metric = parse_metric(**fields)
        bucketed = metric.bucketed_aggregation

        collapsed = render(bucketed.finalize_sql(bucketed.bucket_aggregate))
        jetstream = render(metric.select_expression_from_aggregation)

        assert collapsed != jetstream
        assert collapsed.startswith("CAST(")
        assert collapsed.endswith("AS INT64)")

    def test_cast_as_int_makes_jetstream_int64_too(self):
        metric = parse_metric(aggregation="any", column="a", cast_as_int=True)

        jetstream = render(metric.select_expression_from_aggregation)

        assert jetstream.startswith("CAST(")
        assert jetstream.endswith("AS INT64)")

    def test_cast_as_int_does_not_change_bucketed_aggregation(self):
        with_cast = parse_metric(aggregation="any", column="a", cast_as_int=True)
        without_cast = parse_metric(aggregation="any", column="a")

        assert with_cast.bucketed_aggregation == without_cast.bucketed_aggregation

    @pytest.mark.parametrize(
        "fields",
        [
            {"aggregation": "recency_within", "column": "a", "within_days": 3, "cast_as_int": True},
            {
                "aggregation": "recency_within",
                "column": "days_since_desktop_active",
                "encoding": "days",
                "within_days": 3,
                "cast_as_int": True,
            },
        ],
    )
    def test_cast_as_int_collapses_recency_within_to_the_same_text(self, fields):
        """`recency_within`'s Jetstream expression is already the same COALESCE(MIN(...),
        30) < N text Highwind combines; without cast_as_int only Highwind's finalize casts
        it to INT64, but with cast_as_int both sides do, so the two become byte-identical.
        """
        metric = parse_metric(**fields)
        bucketed = metric.bucketed_aggregation

        collapsed = render(bucketed.finalize_sql(bucketed.bucket_aggregate))
        jetstream = render(metric.select_expression_from_aggregation)

        assert collapsed == jetstream


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
