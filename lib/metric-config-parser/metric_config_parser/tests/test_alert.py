from textwrap import dedent

import pytest
import toml
from cattrs.errors import ClassValidationError

from metric_config_parser.metric import MetricReference
from metric_config_parser.monitoring import MonitoringSpec


class TestAlertSpec:
    def test_alert_definition(self, config_collection):
        config_str = dedent(
            """
            [project]
            alerts = ["test"]
            metrics = ["test_metric"]

            [metrics]
            [metrics.test_metric]
            select_expression = "SELECT 1"
            data_source = "foo"

            [metrics.test_metric.statistics]
            sum = {}

            [data_sources]
            [data_sources.foo]
            from_expression = "test"

            [alerts]
            [alerts.test]
            type = "threshold"
            metrics = ["test_metric"]
            min = [1]
            max = [3]
            percentiles = [1]
            """
        )
        spec = MonitoringSpec.from_dict(toml.loads(config_str))
        assert MetricReference(name="test_metric") in spec.alerts.definitions["test"].metrics
        conf = spec.resolve(experiment=None, configs=config_collection)
        assert conf.alerts[0].name == "test"

    def test_alert_incorrect_type(self):
        config_str = dedent(
            """
            [project]
            alerts = ["test"]

            [alerts]
            [alerts.test]
            type = "foo"
            """
        )

        with pytest.raises(ClassValidationError):
            MonitoringSpec.from_dict(toml.loads(config_str))

    def test_alert_incorrect_config(self):
        config_str = dedent(
            """
            [project]
            alerts = ["test"]

            [alerts]
            [alerts.test]
            type = "threshold"
            metrics = []
            """
        )

        with pytest.raises(ClassValidationError):
            MonitoringSpec.from_dict(toml.loads(config_str))

    def test_alert_incorrect_number_of_thresholds(self):
        config_str = dedent(
            """
            [project]
            alerts = ["test"]

            [alerts]
            [alerts.test]
            type = "threshold"
            min = [1, 2]
            parameters = [1, 2]
            max = [1]
            metrics = []
            """
        )

        with pytest.raises(ClassValidationError):
            MonitoringSpec.from_dict(toml.loads(config_str))
