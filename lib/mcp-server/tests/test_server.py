"""Tests for the MCP server."""

from unittest.mock import MagicMock, patch

import pytest

from metric_hub_mcp.featmon import handle_get_monitored_feature, handle_list_monitored_features
from metric_hub_mcp.metrics import handle_generate_metric_template, handle_list_platforms


@pytest.mark.asyncio
async def test_list_platforms():
    """Test listing platforms."""
    result = await handle_list_platforms()
    assert len(result) == 1
    assert "firefox_desktop" in result[0].text.lower() or "platforms" in result[0].text.lower()


@pytest.mark.asyncio
async def test_generate_simple_metric_template():
    """Test generating a simple metric template."""
    result = await handle_generate_metric_template(
        {
            "metric_name": "test_metric",
            "data_source": "clients_daily",
            "metric_type": "simple",
        }
    )

    assert len(result) == 1
    text = result[0].text

    # Check template contains expected fields
    assert "test_metric" in text
    assert "clients_daily" in text
    assert "friendly_name" in text
    assert "description" in text
    assert "select_expression" in text
    assert "agg_sum" in text


@pytest.mark.asyncio
async def test_generate_derived_metric_template():
    """Test generating a derived metric template."""
    result = await handle_generate_metric_template(
        {
            "metric_name": "derived_metric",
            "data_source": "clients_daily",
            "metric_type": "derived",
        }
    )

    assert len(result) == 1
    text = result[0].text

    # Check template contains derived metric fields
    assert "derived_metric" in text
    assert "depends_on" in text
    assert "metric1" in text


def _make_mock_config(features):
    """Build a minimal mock ConfigCollection with featmon_configs."""
    app_config = MagicMock()
    app_config.slug = "firefox_desktop"
    app_config.spec.dataset = "firefox_desktop"
    app_config.spec.features = features
    app_config.spec.data_sources = {
        "metrics": MagicMock(
            table_name="metrics",
            type="metrics",
            analysis_unit_id="client_info.client_id",
            dimensions={"normalized_channel": {}},
        ),
    }

    collection = MagicMock()
    collection.featmon_configs = [app_config]
    return collection


def _make_feature(key, slug, metrics_by_source):
    feat = MagicMock()
    feat.name = key
    feat.slug = slug
    feat.nimbus_slug.return_value = slug if slug else key
    feat.metrics_by_source = metrics_by_source
    return feat


@pytest.mark.asyncio
async def test_list_monitored_features_returns_all():
    features = {
        "address_autofill_feature": _make_feature(
            "address_autofill_feature",
            "address-autofill-feature",
            {"metrics": {"boolean": {"formautofill_availability": {}}}},
        ),
    }
    mock_config = _make_mock_config(features)

    with patch("metric_hub_mcp.featmon.get_config_collection", return_value=mock_config):
        result = await handle_list_monitored_features({})

    text = result[0].text
    assert "address-autofill-feature" in text
    assert "firefox_desktop" in text


@pytest.mark.asyncio
async def test_list_monitored_features_platform_filter():
    features = {"my_feature": _make_feature("my_feature", None, {})}
    mock_config = _make_mock_config(features)

    with patch("metric_hub_mcp.featmon.get_config_collection", return_value=mock_config):
        result = await handle_list_monitored_features({"platform": "fenix"})

    assert "No monitored features found" in result[0].text


@pytest.mark.asyncio
async def test_get_monitored_feature_found():
    features = {
        "address_autofill_feature": _make_feature(
            "address_autofill_feature",
            "address-autofill-feature",
            {"metrics": {"boolean": {"formautofill_availability": {}}}},
        ),
    }
    mock_config = _make_mock_config(features)

    with patch("metric_hub_mcp.featmon.get_config_collection", return_value=mock_config):
        result = await handle_get_monitored_feature({"feature_slug": "address-autofill-feature"})

    text = result[0].text
    assert "address-autofill-feature" in text
    assert "firefox_desktop" in text
    assert "metrics" in text


@pytest.mark.asyncio
async def test_get_monitored_feature_not_found():
    mock_config = _make_mock_config({})

    with patch("metric_hub_mcp.featmon.get_config_collection", return_value=mock_config):
        result = await handle_get_monitored_feature({"feature_slug": "nonexistent-feature"})

    assert "not found" in result[0].text.lower()
