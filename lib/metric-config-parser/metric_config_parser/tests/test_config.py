import datetime
import shutil
from pathlib import Path
from textwrap import dedent

import pytest
import pytz
import toml
from git import Repo

from metric_config_parser import AnalysisUnit
from metric_config_parser.analysis import AnalysisSpec
from metric_config_parser.config import (
    Config,
    ConfigCollection,
    DefaultConfig,
    DefinitionConfig,
    LocalConfigCollection,
    Outcome,
)
from metric_config_parser.data_source import DataSourceJoinRelationship
from metric_config_parser.errors import DefinitionNotFound
from metric_config_parser.metric import MetricLevel
from metric_config_parser.outcome import OutcomeSpec

TEST_DIR = Path(__file__).parent


class TestConfigIntegration:
    config_str = dedent(
        """
        [metrics]
        weekly = ["active_hours"]

        [metrics.active_hours.statistics.bootstrap_mean]
        """
    )
    spec = AnalysisSpec.from_dict(toml.loads(config_str))

    def test_old_config(self):
        config = Config(
            slug="new_table",
            spec=self.spec,
            last_modified=pytz.UTC.localize(
                datetime.datetime.utcnow() - datetime.timedelta(days=1)
            ),
        )

        config_collection = ConfigCollection([config])

        assert config_collection.spec_for_experiment("new_table") is not None
        assert config_collection.spec_for_outcome("test", "foo") is None
        assert config_collection.get_platform_defaults("desktop") is None
        assert config_collection.get_segment_data_source_definition("foo", "test") is None

    def test_definition_config(self):
        config_str = dedent(
            """
            [metrics.retained]
            select_expression = "COALESCE(COUNT(document_id), 0) > 0"
            data_source = "baseline"

            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            """
        )
        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )

        assert definition

    def test_valid_config_validates(self, experiments):
        config_str = dedent(
            """
            [metrics.active_hours]
            select_expression = "1"
            data_source = "baseline"

            [metrics.active_hours.statistics.bootstrap_mean]

            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            """
        )
        extern = Config(
            slug="cool_experiment",
            spec=self.spec,
            last_modified=datetime.datetime.now(),
        )
        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )

        config_collection = ConfigCollection(
            configs=[extern], outcomes=[], defaults=[], definitions=[definition]
        )
        extern.validate(config_collection, experiments[0])

    def test_busted_config_fails(self, experiments):
        config = dedent(
            """\
            [metrics]
            weekly = ["bogus_metric"]

            [metrics.bogus_metric]
            select_expression = "SUM(fake_column)"
            data_source = "clients_daily"
            statistics = { bootstrap_mean = {} }
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(config))
        extern = Config(
            slug="bad_experiment",
            spec=spec,
            last_modified=datetime.datetime.now(),
        )
        config_collection = ConfigCollection([extern])
        with pytest.raises(DefinitionNotFound):
            extern.validate(config_collection, experiments[0])

    def test_valid_outcome_validates(self):
        config = dedent(
            """\
            friendly_name = "Fred"
            description = "Just your average paleolithic dad."

            [metrics.rocks_mined]
            select_expression = "COALESCE(SUM(pings_aggregated_by_this_row), 0)"
            data_source = "clients_daily"
            statistics = { bootstrap_mean = {} }
            friendly_name = "Rocks mined"
            description = "Number of rocks mined at the quarry"

            [data_sources.clients_daily]
            from_expression = "1"
            """
        )
        spec = OutcomeSpec.from_dict(toml.loads(config))
        extern = Outcome(
            slug="good_outcome",
            spec=spec,
            platform="firefox_desktop",
            commit_hash="0000000",
        )
        extern.validate(configs=ConfigCollection())

    def test_busted_outcome_fails(self):
        config = dedent(
            """\
            friendly_name = "Fred"
            description = "Just your average paleolithic dad."

            [metrics.rocks_mined]
            select_expression = "COALESCE(SUM(fake_column_whoop_whoop), 0)"
            data_source = "clients_daily"
            statistics = { bootstrap_mean = {} }
            friendly_name = "Rocks mined"
            description = "Number of rocks mined at the quarry"
            """
        )
        spec = OutcomeSpec.from_dict(toml.loads(config))
        extern = Outcome(
            slug="bogus_outcome",
            spec=spec,
            platform="firefox_desktop",
            commit_hash="0000000",
        )
        with pytest.raises(DefinitionNotFound):
            extern.validate(configs=ConfigCollection())

    def test_valid_default_config_validates(self):
        config_str = dedent(
            """
            [metrics.active_hours]
            select_expression = "1"
            data_source = "baseline"

            [metrics.active_hours.statistics.bootstrap_mean]

            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            """
        )
        extern = Config(
            slug="cool_experiment",
            spec=self.spec,
            last_modified=datetime.datetime.now(),
        )
        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        extern = DefaultConfig(
            slug="firefox_desktop",
            spec=self.spec,
            last_modified=datetime.datetime.now(),
        )
        extern.validate(configs=ConfigCollection(definitions=[definition]))

    def test_busted_default_config_fails(self):
        config = dedent(
            """\
            [metrics]
            weekly = ["bogus_metric"]

            [metrics.bogus_metric]
            select_expression = "SUM(fake_column)"
            data_source = "clients_daily"
            statistics = { bootstrap_mean = {} }
            """
        )
        spec = AnalysisSpec.from_dict(toml.loads(config))
        extern = DefaultConfig(
            slug="firefox_desktop",
            spec=spec,
            last_modified=datetime.datetime.now(),
        )
        with pytest.raises(DefinitionNotFound):
            extern.validate(configs=ConfigCollection())

    def test_merge_config_collection(self):
        config_str = dedent(
            """
            [metrics.active_hours]
            select_expression = "1"
            data_source = "baseline"

            [metrics.active_hours.statistics.bootstrap_mean]

            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            """
        )
        extern = Config(
            slug="cool_experiment",
            spec=self.spec,
            last_modified=datetime.datetime.now(),
        )
        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        config_collection_1 = ConfigCollection(
            configs=[extern], outcomes=[], defaults=[], definitions=[definition]
        )

        config_str = dedent(
            """
            [metrics.active_hours]
            select_expression = "1"
            data_source = "baseline"

            [metrics.active_hours.statistics.bootstrap_mean]

            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            """
        )
        extern = Config(
            slug="cool_experiment_2",
            spec=self.spec,
            last_modified=datetime.datetime.now(),
        )
        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        config_collection_2 = ConfigCollection(
            configs=[extern], outcomes=[], defaults=[], definitions=[definition]
        )

        config_collection_1.merge(config_collection_2)
        assert config_collection_1.configs[0].slug == "cool_experiment"
        assert config_collection_1.configs[1].slug == "cool_experiment_2"

    def test_merge_config_collection_override(self):
        config_str = dedent(
            """
            [metrics.active_hours]
            select_expression = "1"
            data_source = "baseline"

            [metrics.active_hours.statistics.bootstrap_mean]

            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            """
        )
        extern = Config(
            slug="cool_experiment",
            spec=self.spec,
            last_modified=datetime.datetime.now(),
        )
        config_collection_1 = ConfigCollection(
            configs=[extern], outcomes=[], defaults=[], definitions=[]
        )

        config_str = dedent(
            """
            [metrics.active_hours]
            select_expression = "4"
            data_source = "baseline"

            [metrics.active_hours.statistics.bootstrap_mean]

            [metrics.unenroll]
            select_expression = "3"
            data_source = "baseline"

            [metrics.unenroll.statistics.bootstrap_mean]

            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            """
        )
        extern = Config(
            slug="cool_experiment",
            spec=self.spec,
            last_modified=datetime.datetime.now(),
        )
        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        config_collection_2 = ConfigCollection(
            configs=[extern], outcomes=[], defaults=[], definitions=[definition]
        )

        assert len(config_collection_1.definitions) == 0
        config_collection_1.merge(config_collection_2)

        assert len(config_collection_1.configs) == 1
        assert config_collection_1.configs[0].slug == "cool_experiment"

        assert [
            m
            for slug, m in config_collection_1.definitions[0].spec.metrics.definitions.items()
            if slug == "active_hours"
        ][0].select_expression == "4"
        assert [
            m
            for slug, m in config_collection_1.definitions[0].spec.metrics.definitions.items()
            if slug == "unenroll"
        ][0].select_expression == "3"

    def test_config_collection_from_subdir(self, local_tmp_repo):
        config_collection = ConfigCollection.from_github_repo(
            local_tmp_repo, path="metrics/jetstream"
        )
        assert len(config_collection.configs) > 0

    def test_configs_from_private_repo(self, local_tmp_repo):
        config_collection = ConfigCollection.from_github_repo(
            local_tmp_repo, path="metrics/jetstream", is_private=True
        )
        assert config_collection is not None
        assert config_collection.configs[0].spec.experiment.is_private

    def test_config_from_subdir(self, local_tmp_repo):
        nested_path = Path(local_tmp_repo) / "metrics" / "jetstream"
        config_collection = ConfigCollection.from_github_repo(nested_path)
        assert config_collection is not None

    def test_config_from_subdir_too_deep(self, local_tmp_repo):
        nested_path = Path(local_tmp_repo) / "metrics" / "jetstream"

        with pytest.raises(Exception):
            ConfigCollection.from_github_repo(nested_path, depth=1)

    def test_as_of_broken_commit(self, tmp_path):
        r = Repo.init(tmp_path)
        r.config_writer().set_value("user", "name", "test").release()
        r.config_writer().set_value("user", "email", "test@example.com").release()
        r.config_writer().set_value("commit", "gpgsign", "false").release()

        # check in broken file
        broken_config = dedent(
            """
            friendly_name = "Performance outcomes"
            description = "Outcomes related to performance"

            [metrics]
            weekly = ["speed"]
            overall = ["speed"]

            [metrics.speed]
            data_source = "main"
            select_expression = "1"

            [metrics.speed.statistics.bootstrap_mean]
            """
        )
        outcome_path = tmp_path / "jetstream" / "outcomes" / "firefox_desktop"
        outcome_path.mkdir(parents=True, exist_ok=True)
        (outcome_path / "performance.toml").write_text(broken_config)
        r.git.add(".")
        r.git.commit("-m", "commit", "--date", "Mon 20 Aug 2020 20:19:19 UTC")

        with pytest.raises(Exception):
            ConfigCollection.from_github_repo(tmp_path / "jetstream")

        with pytest.raises(Exception):
            ConfigCollection.from_github_repo(tmp_path / "jetstream").as_of(
                pytz.UTC.localize(datetime.datetime(2023, 5, 21))
            )

        # check in valid files
        shutil.copytree(TEST_DIR / "data", tmp_path, dirs_exist_ok=True)
        r.git.add(".")
        r.git.commit("-m", "commit", "--date", "Mon 25 Aug 2020 20:00:19 UTC")

        configs = ConfigCollection.from_github_repo(tmp_path / "jetstream")
        assert configs.outcomes is not None

        configs = configs.as_of(pytz.UTC.localize(datetime.datetime(2023, 5, 21)))
        assert configs.outcomes is not None

    def test_metric_level(self):
        config_str = dedent(
            """
            [metrics.active_hours]
            select_expression = "1"
            data_source = "baseline"
            owner = "me@example.com"
            category = "test"
            level = "silver"

            [metrics.other_metric]
            select_expression = "1"
            data_source = "baseline"
            owner = ["me@example.com", "you@example.com"]
            category = "test"
            level = "gold"

            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            """
        )

        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        config_collection = ConfigCollection(
            configs=[], outcomes=[], defaults=[], definitions=[definition]
        )

        metric_definition = config_collection.get_metric_definition(
            "active_hours", "firefox_desktop"
        )

        assert metric_definition.level == MetricLevel.SILVER
        assert metric_definition.owner == "me@example.com"
        assert metric_definition.category == "test"

        metric_definition = config_collection.get_metric_definition(
            "other_metric", "firefox_desktop"
        )

        assert metric_definition.level == MetricLevel.GOLD
        assert metric_definition.owner == ["me@example.com", "you@example.com"]
        assert metric_definition.category == "test"

    def test_invalid_metric_level(self):
        config_str = dedent(
            """
            [metrics.active_hours]
            select_expression = "1"
            data_source = "baseline"
            level = "invalid"

            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            """
        )

        with pytest.raises(Exception):
            DefinitionConfig(
                slug="firefox_desktop",
                platform="firefox_desktop",
                spec=AnalysisSpec.from_dict(toml.loads(config_str)),
                last_modified=datetime.datetime.now(),
            )

    def test_valid_analysis_units(self):
        config_str = dedent(
            """
            [metrics.active_hours]
            select_expression = "1"
            data_source = "baseline"
            owner = "me@example.com"
            category = "test"
            analysis_units = ["profile_group_id"]

            [metrics.other_metric]
            select_expression = "1"
            data_source = "baseline"
            owner = ["me@example.com", "you@example.com"]
            category = "test"
            analysis_units = ["client_id", "profile_group_id"]

            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            analysis_units = ["client_id", "profile_group_id"]
            """
        )

        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        config_collection = ConfigCollection(
            configs=[], outcomes=[], defaults=[], definitions=[definition]
        )

        metric_definition = config_collection.get_metric_definition(
            "active_hours", "firefox_desktop"
        )
        assert metric_definition.analysis_units == [AnalysisUnit.PROFILE_GROUP]

        metric_definition = config_collection.get_metric_definition(
            "other_metric", "firefox_desktop"
        )
        assert metric_definition.analysis_units == [
            AnalysisUnit.CLIENT,
            AnalysisUnit.PROFILE_GROUP,
        ]

        data_source_definition = config_collection.get_data_source_definition(
            "baseline", "firefox_desktop"
        )
        assert data_source_definition.analysis_units == [
            AnalysisUnit.CLIENT,
            AnalysisUnit.PROFILE_GROUP,
        ]

    @pytest.mark.parametrize(
        "metric_units,ds_units",
        (
            ("analysis_units = 'client_id'", ""),
            ("analysis_units = ['invalid']", ""),
            ("", "analysis_units = 'client_id'"),
            ("", "analysis_units = ['invalid']"),
        ),
    )
    def test_invalid_analysis_units(self, metric_units, ds_units):
        config_str = dedent(
            f"""
            [metrics.active_hours]
            select_expression = "1"
            data_source = "baseline"
            {metric_units}

            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            {ds_units}
            """
        )
        with pytest.raises(Exception):
            DefinitionConfig(
                slug="firefox_desktop",
                platform="firefox_desktop",
                spec=AnalysisSpec.from_dict(toml.loads(config_str)),
                last_modified=datetime.datetime.now(),
            )

    def test_data_source_joins(self):
        config_str = dedent(
            """
            [data_sources.events]
            from_expression = "mozdata.telemetry.events"
            experiments_column_type = "simple"

            [data_sources.metrics]
            from_expression = "mozdata.telemetry.metrics"
            experiments_column_type = "simple"

            [data_sources.baseline]
            from_expression = "mozdata.telemetry.baseline"
            experiments_column_type = "simple"

            [data_sources.baseline.joins.metrics]
            on_expression = "metrics.client_id = baseline.client_id"
            relationship = "many_to_one"

            [data_sources.baseline.joins.events]
            """
        )

        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        config_collection = ConfigCollection(
            configs=[], outcomes=[], defaults=[], definitions=[definition]
        )

        data_source = config_collection.get_data_source_definition(
            "baseline", "firefox_desktop"
        ).resolve(definition.spec, None, config_collection)

        assert len(data_source.joins) == 2
        assert data_source.joins[0].data_source.name == "metrics"
        assert data_source.joins[0].on_expression == "metrics.client_id = baseline.client_id"
        assert data_source.joins[0].relationship == DataSourceJoinRelationship.MANY_TO_ONE

        assert data_source.joins[1].data_source.name == "events"

    def test_data_source_joins_invalid(self):
        config_str = dedent(
            """
            [data_sources.baseline]
            from_expression = "mozdata.telemetry.baseline"
            experiments_column_type = "simple"

            [data_sources.baseline.joins.non_existing]
            relationship = "many_to_one"
            """
        )

        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        config_collection = ConfigCollection(
            configs=[], outcomes=[], defaults=[], definitions=[definition]
        )

        with pytest.raises(Exception):
            config_collection.get_data_source_definition("baseline", "firefox_desktop").resolve(
                definition.spec, None, config_collection
            )

    def test_data_source_joins_circular_dependency(self):
        config_str = dedent(
            """
            [data_sources.baseline]
            from_expression = "mozdata.telemetry.baseline"
            experiments_column_type = "simple"

            [data_sources.metrics]
            from_expression = "mozdata.telemetry.metrics"
            experiments_column_type = "simple"

            [data_sources.baseline.joins.metrics]

            [data_sources.metrics.joins.baseline]
            """
        )

        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        config_collection = ConfigCollection(
            configs=[], outcomes=[], defaults=[], definitions=[definition]
        )

        with pytest.raises(Exception):
            config_collection.get_data_source_definition("baseline", "firefox_desktop").resolve(
                definition.spec, None, config_collection
            )

    def test_invalid_wildcard_in_data_source(self):
        # needs to be [data_sources.'baseline_*']
        config_str = dedent(
            """
            [data_sources.baseline_*]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            """
        )

        with pytest.raises(ValueError):
            DefinitionConfig(
                slug="firefox_desktop",
                platform="firefox_desktop",
                spec=AnalysisSpec.from_dict(toml.loads(config_str)),
                last_modified=datetime.datetime.now(),
            )

    def test_merge_with_wildcards(self):
        config_str = dedent(
            """
            [metrics.test_metric]
            select_expression = 1
            category = "test"

            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            """
        )

        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        config_collection_1 = ConfigCollection(
            configs=[], outcomes=[], defaults=[], definitions=[definition]
        )

        config_str = dedent(
            """
            [data_sources.'*']
            experiments_column_type = "none"

            [metrics.'test_*']
            data_source = "baseline"
            category = "test_overwrite_first"

            [metrics.'test_*'.statistics.bootstrap_mean]

            [metrics.'test_me*']
            category = "test_overwrite_second"
            """
        )
        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        config_collection_2 = ConfigCollection(
            configs=[], outcomes=[], defaults=[], definitions=[definition]
        )

        config_collection_1.get_metric_definition(
            "test_metric", "firefox_desktop"
        ).data_source is None
        assert (
            config_collection_1.get_data_source_definition(
                "baseline", "firefox_desktop"
            ).experiments_column_type
            == "simple"
        )

        config_collection_1.merge(config_collection_2)
        assert (
            config_collection_1.get_data_source_definition("baseline", "firefox_desktop").name
            == "baseline"
        )
        assert (
            config_collection_1.get_data_source_definition(
                "baseline", "firefox_desktop"
            ).experiments_column_type
            == "none"
        )
        assert config_collection_1.get_data_source_definition("*", "firefox_desktop") is None
        assert (
            config_collection_1.get_metric_definition(
                "test_metric", "firefox_desktop"
            ).data_source.name
            == "baseline"
        )
        assert (
            "bootstrap_mean"
            in config_collection_1.get_metric_definition(
                "test_metric", "firefox_desktop"
            ).statistics
        )
        assert (
            config_collection_1.get_metric_definition("test_metric", "firefox_desktop").category
            == "test_overwrite_second"
        )

    def test_merge_with_wildcards_invalid(self):
        config_str = dedent(
            """
            [data_sources.baseline]
            from_expression = "mozdata.search.baseline"
            experiments_column_type = "simple"
            """
        )

        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        config_collection_1 = ConfigCollection(
            configs=[], outcomes=[], defaults=[], definitions=[definition]
        )

        config_str = dedent(
            """
            [data_sources.'invalid_*']
            experiments_column_type = "none"
            """
        )
        definition = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str)),
            last_modified=datetime.datetime.now(),
        )
        config_collection_2 = ConfigCollection(
            configs=[], outcomes=[], defaults=[], definitions=[definition]
        )

        config_collection_1.merge(config_collection_2)
        assert (
            config_collection_1.get_data_source_definition("baseline", "firefox_desktop").name
            == "baseline"
        )
        assert (
            config_collection_1.get_data_source_definition(
                "baseline", "firefox_desktop"
            ).experiments_column_type
            == "simple"
        )
        assert (
            config_collection_1.get_data_source_definition("invalid_*", "firefox_desktop") is None
        )

    def test_get_segments_for_app_with_toml(self):
        config_str_desktop = """
        [segments.my_cool_segment]
        data_source = "my_cool_data_source"
        select_expression = "{{agg_any('1')}}"

        [segments.another_segment]
        data_source = "another_data_source"
        select_expression = "{{agg_sum('2')}}"

        [segments.data_sources.my_cool_data_source]
        from_expression = "max(attr_source is not null)"

        [segments.data_sources.another_data_source]
        from_expression = "max(attr_source is null)"
        """

        config_str_fenix = """
        [segments.fenix_segment]
        data_source = "fenix_data_source"
        select_expression = "{{agg_count('3')}}"

        [segments.data_sources.fenix_data_source]
        from_expression = "min(attr_source is not null)"
        """

        definition_desktop = DefinitionConfig(
            slug="firefox_desktop",
            platform="firefox_desktop",
            spec=AnalysisSpec.from_dict(toml.loads(config_str_desktop)),
            last_modified=datetime.datetime.now(),
        )

        definition_fenix = DefinitionConfig(
            slug="fenix",
            platform="fenix",
            spec=AnalysisSpec.from_dict(toml.loads(config_str_fenix)),
            last_modified=datetime.datetime.now(),
        )

        config_collection = ConfigCollection(
            configs=[],
            outcomes=[],
            defaults=[],
            definitions=[definition_desktop, definition_fenix],
        )

        segments_desktop = config_collection.get_segments_for_app("firefox_desktop")
        assert len(segments_desktop) == 2

        segment_slugs_desktop = [seg.name for seg in segments_desktop]
        assert "my_cool_segment" in segment_slugs_desktop
        assert "another_segment" in segment_slugs_desktop

        segments_fenix = config_collection.get_segments_for_app("fenix")
        assert len(segments_fenix) == 1

        segment_slugs_fenix = [seg.name for seg in segments_fenix]
        assert "fenix_segment" in segment_slugs_fenix

    def test_local_config_collection_from_local_path(self):
        config_collection = LocalConfigCollection.from_local_path(TEST_DIR / "data")
        segments = [s.name for s in config_collection.get_segments_for_app("firefox_desktop")]
        assert "regular_users_v3" in segments
        assert len(segments) == 1

        outcomes = [o.slug for o in config_collection.outcomes]
        assert len(outcomes) == 0

        test_metric = config_collection.get_metric_definition("active_hours", "firefox_desktop")
        assert test_metric.name == "active_hours"
        assert test_metric.select_expression == '{{agg_sum("active_hours_sum")}}'
        assert test_metric.data_source.name == "clients_daily"

        cc_jetstream = LocalConfigCollection.from_local_path(TEST_DIR / "data" / "jetstream")
        config_collection.merge(cc_jetstream)

        outcomes = [o.slug for o in config_collection.outcomes]
        assert len(outcomes) == 4
