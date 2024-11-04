from pathlib import Path

import pytest

ROOT = Path(__file__).parent
TEST_DATA = ROOT / "sql"


def test_generate_query_single_metric(config_collection):
    assert (
        config_collection.get_metrics_sql(metrics=["active_hours"], platform="firefox_desktop")
        == (TEST_DATA / "test_generate_query_single_metric.expected.sql").read_text()
    )


def test_generate_query_multiple_metrics(config_collection):
    assert (
        config_collection.get_metrics_sql(
            metrics=["active_hours", "days_of_use"], platform="firefox_desktop"
        )
        == (TEST_DATA / "test_generate_query_multiple_metrics.expected.sql").read_text()
    )


def test_generate_query_with_parameters(config_collection):
    assert (
        config_collection.get_metrics_sql(
            metrics=["active_hours", "days_of_use"],
            platform="firefox_desktop",
            group_by=["build_id", "sample_id"],
            where="submission_date = '2023-01-01' AND normalized_channel = 'release'",
        )
        == (TEST_DATA / "test_generate_query_with_parameters.expected.sql").read_text()
    )

    assert (
        config_collection.get_metrics_sql(
            metrics=["active_hours", "days_of_use"],
            platform="firefox_desktop",
            group_by={"build_id": "build_id", "sample_id": "sample_id"},
            where="submission_date = '2023-01-01' AND normalized_channel = 'release'",
        )
        == (TEST_DATA / "test_generate_query_with_parameters.expected.sql").read_text()
    )


def test_generate_query_with_multiple_metrics_different_data_sources(config_collection):
    assert (
        config_collection.get_metrics_sql(
            metrics=["active_hours", "days_of_use", "unenroll", "view_about_logins"],
            platform="firefox_desktop",
            group_by=["build_id", "sample_id"],
            where="submission_date = '2023-01-01' AND normalized_channel = 'release'",
        )
        == (
            TEST_DATA
            / "test_generate_query_with_multiple_metrics_different_data_sources.expected.sql"
        ).read_text()
    )


def test_generate_query_without_client_id_submission_date(config_collection):
    assert (
        config_collection.get_metrics_sql(
            metrics=["active_hours"],
            platform="firefox_desktop",
            group_by=["build_id"],
            where="submission_date = '2023-01-01' AND normalized_channel = 'release'",
            group_by_client_id=False,
            group_by_submission_date=False,
        )
        == (TEST_DATA / "test_generate_query_without_client_id.expected.sql").read_text()
    )


def test_generate_query_with_null_client_id(config_collection):
    assert (
        config_collection.get_metrics_sql(
            metrics=["cohort_clients_in_cohort"],
            platform="firefox_desktop",
        )
        == (TEST_DATA / "test_generate_query_with_null_client_id.expected.sql").read_text()
    )


def test_no_metric_definition_found(config_collection):
    with pytest.raises(ValueError):
        config_collection.get_metrics_sql(metrics=["doesnt-exist"], platform="firefox_desktop")


def test_data_source(config_collection):
    assert (
        config_collection.get_data_source_sql(
            data_source="main",
            platform="firefox_desktop",
            where="submission_date = '2023-01-01'",
        )
        == (TEST_DATA / "test_generate_data_source.expected.sql").read_text()
    )


def test_data_source_not_found(config_collection):
    with pytest.raises(ValueError):
        config_collection.get_data_source_sql(
            data_source="non-existing", platform="firefox_desktop"
        )


def test_data_source_with_join(config_collection):
    assert (
        config_collection.get_data_source_sql(
            data_source="joined_baseline",
            platform="firefox_desktop",
            where="submission_date = '2023-01-01'",
        )
        == (TEST_DATA / "test_generate_data_source_with_join.expected.sql").read_text()
    )


def test_data_source_with_multiple_join(config_collection):
    assert (
        config_collection.get_data_source_sql(
            data_source="multiple_joined_baseline",
            platform="firefox_desktop",
            where="submission_date = '2023-01-01'",
        )
        == (TEST_DATA / "test_generate_data_source_with_multi_join.expected.sql").read_text()
    )


def test_metric_with_joined_data_source(config_collection):
    assert (
        config_collection.get_metrics_sql(
            metrics=["joined_metric"],
            platform="firefox_desktop",
            where="submission_date = '2023-01-01' AND normalized_channel = 'release'",
            group_by_client_id=True,
            group_by_submission_date=False,
        )
        == (TEST_DATA / "test_generate_query_with_joined_data_sources.expected.sql").read_text()
    )
