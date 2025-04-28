from datetime import datetime
from pathlib import Path

from pytz import UTC

from metric_config_parser.analysis import AnalysisSpec
from metric_config_parser.config import ConfigCollection
from metric_config_parser.experiment import Channel, Experiment
from metric_config_parser.metric import AnalysisPeriod


class TestConfigIntegration:
    def test_overall_retention_regression(self):
        config_collection = ConfigCollection.from_github_repos(
            [
                "https://github.com/mozilla/metric-hub",
                "https://github.com/mozilla/metric-hub/tree/main/jetstream",
            ]
        )
        experiment_slug = "ios-onboarding-search-widget"
        config_collection.as_of(datetime.fromisoformat("2023-11-16T21:44:49+00:00"))
        experiment = Experiment(
            experimenter_slug=None,
            normandy_slug=experiment_slug,
            type="v6",
            status="Complete",
            branches=["control", "treatment-a", "treatment-b"],
            reference_branch="control",
            is_high_population=False,
            start_date=datetime(2023, 9, 8),
            proposed_enrollment=14,
            enrollment_end_date=datetime(2023, 9, 19),
            end_date=datetime(2023, 10, 16),
            app_name="firefox_ios",
            channel=Channel.RELEASE,
            is_enrollment_paused=True,
            outcomes=["onboarding", "default_browser"],
        )
        spec = AnalysisSpec.default_for_experiment(experiment, config_collection)
        experiment_config = spec.resolve(experiment, config_collection)

        overall_metric_names = [
            summary.metric.name for summary in experiment_config.metrics[AnalysisPeriod.OVERALL]
        ]
        assert "retained" not in overall_metric_names
        assert "opened_as_default" in overall_metric_names
        assert "default_browser_card_go_to_settings_pressed" in overall_metric_names

        weekly_metric_names = [
            summary.metric.name for summary in experiment_config.metrics[AnalysisPeriod.WEEK]
        ]
        assert "retained" in weekly_metric_names
        assert "opened_as_default" in weekly_metric_names
        assert "default_browser_card_go_to_settings_pressed" in weekly_metric_names

    def test_configs_from_repo(self):
        config_collection = ConfigCollection.from_github_repos(
            ["https://github.com/mozilla/metric-hub"]
        )
        assert config_collection is not None
        assert config_collection.get_platform_defaults("firefox_desktop") is None
        assert config_collection.spec_for_outcome("test", "firefox_desktop") is None
        assert (
            config_collection.get_data_source_definition("clients_daily", "firefox_desktop")
            is not None
        )
        assert config_collection.get_metric_definition("baseline_ping_count", "fenix") is not None
        assert config_collection.get_metric_definition("not_exist", "firefox_desktop") is None
        assert (
            config_collection.get_segment_definition("regular_users_v3", "firefox_desktop")
            is not None
        )
        assert config_collection.get_segments_for_app("firefox_desktop") is not None

    def test_configs_from_multiple_repos(self):
        config_collection = ConfigCollection.from_github_repos(
            repo_urls=[ConfigCollection.repo_url, ConfigCollection.repo_url]
        )
        assert config_collection is not None
        assert config_collection.functions is not None

        default_collection = ConfigCollection.from_github_repo()
        assert len(config_collection.configs) == len(default_collection.configs)
        assert config_collection.outcomes == default_collection.outcomes
        assert len(config_collection.defaults) == len(default_collection.defaults)
        assert len(config_collection.definitions) == len(default_collection.definitions)

    def test_config_from_repo_tree(self):
        config_collection = ConfigCollection.from_github_repo(
            "https://github.com/mozilla/metric-hub/tree/main/jetstream"
        )
        assert config_collection.configs is not None

    def test_config_from_repo_tree_multiple(self):
        config_collection = ConfigCollection.from_github_repos(
            repo_urls=[
                ConfigCollection.repo_url,
                "https://github.com/mozilla/metric-hub/tree/main/jetstream",
            ]
        )

        assert config_collection.configs is not None
        assert len(config_collection.definitions) > 0

    def test_config_collection_from_branch(self):
        config_collection = ConfigCollection.from_github_repos(
            [
                "https://github.com/mozilla/metric-hub/tree/main",
                "https://github.com/mozilla/metric-hub/tree/main/jetstream/",
            ],
        )
        assert len(config_collection.configs) > 0

    def test_config_as_of(self):
        config_collection = ConfigCollection.from_github_repo(
            "https://github.com/mozilla/metric-hub/tree/main/jetstream"
        ).as_of(
            UTC.localize(datetime(2023, 5, 15))
        )  # 6a052aea23e7e2332a20c992b2e6f07468c3d161

        assert config_collection is not None
        assert config_collection.spec_for_outcome("networking", "firefox_desktop") is None

        config_collection = config_collection.as_of(UTC.localize(datetime(2023, 5, 30)))  # 0f92ef5
        assert config_collection.spec_for_outcome("networking", "firefox_desktop") is not None

    def test_config_as_of_multiple_repos(self):
        config_collection = ConfigCollection.from_github_repos(
            repo_urls=[
                ConfigCollection.repo_url,
                "https://github.com/mozilla/metric-hub/tree/main/jetstream",
            ]
        )

        assert config_collection is not None
        assert config_collection.spec_for_outcome("networking", "firefox_desktop") is not None
        assert config_collection.get_metric_definition("daily_active_users_v2", "fenix") is not None

        config_collection = config_collection.as_of(
            UTC.localize(datetime(2023, 5, 15))
        )  # 6a052aea23e7e2332a20c992b2e6f07468c3d161

        assert config_collection.spec_for_outcome("networking", "firefox_desktop") is None
        assert config_collection.get_metric_definition("daily_active_users_v2", "fenix") is None

        config_collection = config_collection.as_of(
            UTC.localize(datetime(2023, 5, 25, 20, 0, 0))  # 2fa5433
        )

        assert config_collection.spec_for_outcome("networking", "firefox_desktop") is None
        assert config_collection.get_metric_definition("daily_active_users_v2", "fenix") is not None

    def test_remove_tmp_dir_on_destruct(self):
        config_collection = ConfigCollection.from_github_repos(
            repo_urls=[
                ConfigCollection.repo_url,
                "https://github.com/mozilla/metric-hub/tree/main/jetstream",
            ]
        )

        tmp_dirs = [Path(r.repo.git_dir).parent for r in config_collection.repos]

        for tmp_dir in tmp_dirs:
            assert tmp_dir.exists()

        del config_collection

        for tmp_dir in tmp_dirs:
            assert tmp_dir.exists() is False
