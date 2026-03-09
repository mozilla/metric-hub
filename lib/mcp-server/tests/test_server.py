"""Tests for the MCP server."""

import pytest
from metric_hub_mcp.server import (
    handle_list_platforms,
    handle_generate_metric_template,
    handle_validate_metric_config,
)


@pytest.mark.asyncio
async def test_list_platforms():
    """Test listing platforms."""
    result = await handle_list_platforms()
    assert len(result) == 1
    assert "firefox_desktop" in result[0].text.lower() or "platforms" in result[0].text.lower()


@pytest.mark.asyncio
async def test_generate_simple_metric_template():
    """Test generating a simple metric template."""
    result = await handle_generate_metric_template({
        "metric_name": "test_metric",
        "data_source": "clients_daily",
        "metric_type": "simple",
    })

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
    result = await handle_generate_metric_template({
        "metric_name": "derived_metric",
        "data_source": "clients_daily",
        "metric_type": "derived",
    })

    assert len(result) == 1
    text = result[0].text

    # Check template contains derived metric fields
    assert "derived_metric" in text
    assert "depends_on" in text
    assert "metric1" in text


@pytest.mark.asyncio
async def test_validate_valid_metric():
    """Test validating a valid metric configuration."""
    config = """
[metrics.test_metric]
friendly_name = "Test Metric"
description = "A test metric"
data_source = "clients_daily"
select_expression = '{{agg_sum("field")}}'
category = "test"
"""

    result = await handle_validate_metric_config({
        "config_toml": config,
        "platform": "firefox_desktop",
    })

    assert len(result) == 1
    text = result[0].text
    assert "valid" in text.lower() or "✅" in text


@pytest.mark.asyncio
async def test_validate_invalid_metric():
    """Test validating an invalid metric configuration."""
    config = """
[metrics.invalid_metric]
# Missing required fields
friendly_name = "Invalid Metric"
"""

    result = await handle_validate_metric_config({
        "config_toml": config,
        "platform": "firefox_desktop",
    })

    assert len(result) == 1
    text = result[0].text
    assert "error" in text.lower() or "❌" in text


@pytest.mark.asyncio
async def test_validate_malformed_toml():
    """Test validating malformed TOML."""
    config = """
[metrics.bad
this is not valid toml
"""

    result = await handle_validate_metric_config({
        "config_toml": config,
        "platform": "firefox_desktop",
    })

    assert len(result) == 1
    text = result[0].text
    assert "error" in text.lower() or "❌" in text
    assert "parse" in text.lower() or "toml" in text.lower()
