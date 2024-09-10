import pytest

from metric_config_parser.metric import AnalysisPeriod, MetricDefinition
from metric_config_parser.parameter import ParameterDefinition


class TestMetricDefinition:
    @pytest.mark.parametrize(
        "input,expected",
        (
            (
                [
                    {"param": ParameterDefinition(name="param", value="1")},
                    "param = {{ parameters.param }}",
                ],
                "param = 1",
            ),
            (
                [
                    {"param": ParameterDefinition(name="param", value="1")},
                    "{{ parameters.param }}",
                ],
                "1",
            ),
            ([{"param": ParameterDefinition(name="param", value="1")}, ""], ""),
            (
                [
                    {
                        "param": ParameterDefinition(
                            name="param",
                            distinct_by_branch=True,
                            value={"branch_1": "1"},
                        )
                    },
                    "",
                ],
                "",
            ),
            (
                [
                    {
                        "param": ParameterDefinition(
                            name="param",
                            distinct_by_branch=True,
                            value={"branch_1": "1"},
                        )
                    },
                    "{{parameters.param}}",
                ],
                'CASE e.branch WHEN "branch_1" THEN "1" END',
            ),
            (
                [
                    {
                        "param": ParameterDefinition(
                            name="param",
                            distinct_by_branch=True,
                            value={
                                "branch_1": "1",
                                "branch_2": "2",
                            },
                        )
                    },
                    "COUNTIF(id = {{parameters.param}})",
                ],
                (
                    """COUNTIF(id = CASE e.branch """
                    """WHEN "branch_1" THEN "1" WHEN "branch_2" THEN "2" END)"""
                ),
            ),
        ),
    )
    def test_generate_select_expression(self, input, expected, config_collection):
        """
        In case ParameterDefinition object is passed we just return the value,
        if List[ParameterDefinition] is given then we need to generate the whole select statement
        """

        param_definition, select_template = input

        actual = MetricDefinition.generate_select_expression(
            param_definition, select_template, config_collection
        )
        assert expected == actual

    def test_analysis_periods_conflicts(self):
        for test_period in AnalysisPeriod:
            for period in [p for p in AnalysisPeriod if p != test_period]:
                assert not period.value.startswith(f"{test_period.value}_")
