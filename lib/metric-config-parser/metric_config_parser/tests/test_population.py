from datetime import datetime
from textwrap import dedent

import pytz
import toml

from metric_config_parser.monitoring import MonitoringSpec
from metric_config_parser.project import MonitoringPeriod


class TestPopulationSpec:
    def test_overwrite_population(self, config_collection):
        config_str = dedent(
            """
            [project]
            name = "foo"
            xaxis = "build_id"
            metrics = []
            start_date = "2022-01-01"
            end_date = "2022-02-01"

            [project.population]
            data_source = "foo"
            boolean_pref = "TRUE"
            branches = ["treatment"]
            dimensions = ["os"]
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

        config_str = dedent(
            """
            [project]
            name = "foo bar"
            end_date = "2022-03-01"
            skip_default_metrics = true

            [project.population]
            boolean_pref = "FALSE"
            branches = ["test-1"]
            """
        )

        spec2 = MonitoringSpec.from_dict(toml.loads(config_str))
        spec.merge(spec2)
        cfg = spec.resolve(experiment=None, configs=config_collection)

        assert cfg.project.name == "foo bar"
        assert cfg.project.xaxis == MonitoringPeriod.BUILD_ID
        assert cfg.project.start_date == datetime(2022, 1, 1, tzinfo=pytz.utc)
        assert cfg.project.end_date == datetime(2022, 3, 1, tzinfo=pytz.utc)
        assert cfg.project.population.data_source.name == "foo"
        assert cfg.project.population.boolean_pref == "FALSE"
        assert cfg.project.population.branches == ["treatment"]
        assert cfg.project.skip_default_metrics
        assert len(cfg.dimensions) == 1
