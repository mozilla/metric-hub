from metric_config_parser.parameter import ParameterDefinition, ParameterSpec


class TestParameterSpec:
    """
    Class for testing functionality related to ParameterSpec
    """

    def test_from_dict(self):
        test_spec = {
            "param_1": {"name": "test"},
        }

        actual = ParameterSpec.from_dict(test_spec)
        assert type(actual) is ParameterSpec
        assert type(actual.definitions["param_1"]) is ParameterDefinition
