import pytest

from metric_config_parser.data_source import DataSource, render_from_expression


class FakeExperiment:
    normandy_slug = "my-slug"


class TestRenderFromExpression:
    def test_no_braces_is_identity(self):
        expr = "mozdata.telemetry.events"
        assert render_from_expression("t", expr, None) == expr

    def test_syntax_error_is_identity(self):
        # `{{` used as a str.format literal-brace escape, e.g. an add-on GUID.
        expr = "(SELECT '{{d10d0bf8-f5b5-c8b4-a8b2-2b9879e08c5d}}')"
        assert render_from_expression("t", expr, None) == expr

    def test_no_variables_is_identity(self):
        expr = r"REGEXP_CONTAINS(x, r'\d{{4}}')"
        assert render_from_expression("t", expr, None) == expr

    def test_renders_experiment_reference(self):
        expr = "(SELECT '{{experiment.normandy_slug}}')"
        assert render_from_expression("t", expr, FakeExperiment()) == "(SELECT 'my-slug')"

    def test_without_experiment_raises(self):
        expr = "(SELECT '{{experiment.normandy_slug}}')"
        with pytest.raises(ValueError, match="no experiment is available"):
            render_from_expression("t", expr, None)

    def test_unrelated_placeholder_is_left_unrendered(self):
        expr = "(SELECT '{{slug}}')"
        assert render_from_expression("t", expr, None) == expr

    def test_unknown_variable_alongside_experiment_raises(self):
        expr = "(SELECT '{{experiment.normandy_slug}}' WHERE x = '{{nope}}')"
        with pytest.raises(ValueError, match="nope"):
            render_from_expression("t", expr, FakeExperiment())


class TestDataSource:
    def test_rejects_unrendered_experiment_template(self):
        with pytest.raises(ValueError, match="no experiment is available"):
            DataSource(name="x", from_expression="a {{experiment.normandy_slug}} b")

    def test_from_expr_for_unsupported_placeholder_message(self):
        with pytest.raises(ValueError, match="unsupported placeholder"):
            DataSource(name="x", from_expression="a {experiment.normandy_slug} b")

    def test_from_expr_for_missing_default_dataset_message(self):
        with pytest.raises(ValueError, match="default_dataset"):
            DataSource(name="x", from_expression="mozdata.{dataset}.x")

    def test_from_expr_for_with_dataset(self):
        ds = DataSource(
            name="x", from_expression="mozdata.{dataset}.x", default_dataset="telemetry"
        )
        assert ds.from_expr_for(None) == "mozdata.telemetry.x"
        assert ds.from_expr_for("other") == "mozdata.other.x"

    def test_from_expr_for_literal_braces(self):
        ds = DataSource(
            name="x", from_expression="(SELECT '{{d10d0bf8-f5b5-c8b4-a8b2-2b9879e08c5d}}')"
        )
        assert ds.from_expr_for(None) == "(SELECT '{d10d0bf8-f5b5-c8b4-a8b2-2b9879e08c5d}')"
