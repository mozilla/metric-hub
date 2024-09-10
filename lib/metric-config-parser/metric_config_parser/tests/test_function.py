from textwrap import dedent

import pytest
import toml

from metric_config_parser.function import FunctionsSpec


class TestFunction:
    def test_parse_valid_function_config(self):
        config_str = dedent(
            '''
            [functions]

            [functions.agg_sum]
            definition = "COALESCE(SUM({select_expr}), 0)"

            [functions.agg_any]
            definition = "COALESCE(LOGICAL_OR({select_expr}), FALSE)"

            [functions.agg_histogram_mean]
            definition = """
                SAFE_DIVIDE(
                    SUM(CAST(JSON_EXTRACT_SCALAR({select_expr}, "$.sum") AS int64)),
                    SUM((SELECT SUM(value) FROM UNNEST(mozfun.hist.extract({select_expr}).values)))
                )
            """
        '''
        )
        function_spec = FunctionsSpec.from_dict(toml.loads(config_str))

        assert function_spec.functions["agg_sum"].slug == "agg_sum"
        assert function_spec.functions["agg_sum"].definition("1") == "COALESCE(SUM(1), 0)"

        assert function_spec.functions["agg_any"].slug == "agg_any"
        assert (
            function_spec.functions["agg_any"].definition("1") == "COALESCE(LOGICAL_OR(1), FALSE)"
        )

        assert function_spec.functions["agg_histogram_mean"].slug == "agg_histogram_mean"

    def test_parse_invalid_function_config(self):
        config_str = dedent(
            """
            [functions]

            [functions.agg_sum]
        """
        )

        with pytest.raises(KeyError):
            FunctionsSpec.from_dict(toml.loads(config_str))
