from textwrap import dedent

import pytest
import toml
from cattrs.errors import ClassValidationError

from metric_config_parser.metric import MetricReference
from metric_config_parser.monitoring import MonitoringSpec


class TestProjectSpec:
    def test_group_by_fail(self, config_collection):
        config_str = dedent(
            """
            [project]
            name = "foo"
            xaxis = "build_id"
            metrics = []

            [project.population]
            data_source = "foo"
            group_by_dimension = "os"

            [data_sources]
            [data_sources.foo]
            from_expression = "test"

            [dimensions]
            [dimensions.os]
            select_expression = "os"
            data_source = "foo"
            """
        )

        spec = MonitoringSpec.from_dict(toml.loads(config_str))

        with pytest.raises(ValueError):
            spec.resolve(experiment=None, configs=config_collection)

    def test_bad_project_dates(self):
        config_str = dedent(
            """
            [project]
            start_date = "My birthday"
            """
        )

        with pytest.raises(ClassValidationError):
            MonitoringSpec.from_dict(toml.loads(config_str))

    def test_bad_project_xaxis(self):
        config_str = dedent(
            """
            [project]
            xaxis = "Nothing"
            """
        )

        with pytest.raises(ClassValidationError):
            MonitoringSpec.from_dict(toml.loads(config_str))

    def test_metric_groups(self, config_collection):
        config_str = dedent(
            """
            [project]
            name = "foo"
            metrics = ["foo", "bar"]

            [project.metric_groups.foo]
            friendly_name = "Fooooo"
            metrics = [
                "foo",
                "bar"
            ]

            [project.population]
            data_source = "foo"

            [data_sources]
            [data_sources.foo]
            from_expression = "test"

            [metrics]
            [metrics.foo]
            select_expression = "foo"
            data_source = "foo"

            [metrics.foo.statistics]
            sum = {}

            [metrics.bar]
            select_expression = "bar"
            data_source = "foo"

            [metrics.bar.statistics]
            sum = {}
            """
        )

        spec = MonitoringSpec.from_dict(toml.loads(config_str))
        config = spec.resolve(experiment=None, configs=config_collection)

        assert len(config.project.metric_groups) == 1
        assert config.project.metric_groups[0].name == "foo"
        assert MetricReference("foo") in config.project.metric_groups[0].metrics
        assert MetricReference("bar") in config.project.metric_groups[0].metrics
