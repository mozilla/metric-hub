# Metric Hub MCP Server

An MCP (Model Context Protocol) server for Mozilla Metric Hub that enables AI assistants like Gemini to query, create, and validate metrics configurations.

## Features

- **Query Metrics**: Browse and search metrics across all platforms
- **Data Source Information**: Get details about available data sources
- **Validation**: Validate metric configurations before deployment
- **Templates**: Generate templates for creating new metrics
- **SQL Generation**: View generated SQL for metrics

## Installation

### Prerequisites

- Python 3.10 or higher
- Access to the metric-hub repository

### Install from source

If you're working with the latest development version of metric-config-parser:

```bash
# First, install the local metric-config-parser
cd /Users/anna/mydata/metric-hub/lib/metric-config-parser
pip install -e .

# Then install the MCP server
cd /Users/anna/mydata/metric-hub/lib/mcp-server
pip install -e .
```

Or if you want to use the published version from PyPI:

```bash
cd /Users/anna/mydata/metric-hub/lib/mcp-server
pip install .
```

## Usage

### Running the Server

The MCP server communicates via stdio and is designed to be used with MCP clients like Claude Desktop or Gemini.

```bash
metric-hub-mcp
```

### Configuration for Gemini

Add the following to your MCP client configuration:

**For Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "metric-hub": {
      "command": "metric-hub-mcp"
    }
  }
}
```

**For other MCP clients**, configure the server to run the `metric-hub-mcp` command via stdio.

## Available Tools

### 1. `list_platforms`

List all available platforms/products with metric definitions.

**Example:**
```
Use list_platforms to see all platforms
```

### 2. `list_metrics`

List all metrics for a specific platform, optionally filtered by category.

**Parameters:**
- `platform` (required): Platform name (e.g., 'firefox_desktop', 'fenix', 'ads')
- `category` (optional): Filter by category (e.g., 'search', 'performance')

**Example:**
```
List all search metrics for firefox_desktop
```

### 3. `get_metric`

Get detailed information about a specific metric.

**Parameters:**
- `platform` (required): Platform name
- `metric_name` (required): Name of the metric

**Example:**
```
Show me details about the active_hours metric in firefox_desktop
```

### 4. `list_data_sources`

List all data sources for a specific platform.

**Parameters:**
- `platform` (required): Platform name

**Example:**
```
What data sources are available for fenix?
```

### 5. `get_data_source`

Get detailed information about a specific data source.

**Parameters:**
- `platform` (required): Platform name
- `data_source_name` (required): Name of the data source

**Example:**
```
Show me details about the clients_daily data source
```

### 6. `search_metrics`

Search for metrics across all platforms by name or description.

**Parameters:**
- `query` (required): Search query
- `platform` (optional): Limit search to specific platform

**Example:**
```
Search for metrics related to "search count"
```

### 7. `validate_metric_config`

Validate a metric configuration in TOML format.

**Parameters:**
- `config_toml` (required): TOML configuration string
- `platform` (required): Platform name for context

**Example:**
```
Validate this metric config:
[metrics.test_metric]
friendly_name = "Test Metric"
data_source = "clients_daily"
select_expression = '{{agg_sum("field")}}'
```

### 8. `generate_metric_template`

Generate a template for creating a new metric.

**Parameters:**
- `metric_name` (required): Name for the new metric (snake_case)
- `data_source` (required): Data source to use
- `metric_type` (required): Type of metric ('simple', 'derived', or 'custom')

**Example:**
```
Generate a template for a simple metric called daily_active_users using clients_daily
```

### 9. `get_metric_sql`

Generate SQL query for a metric.

**Parameters:**
- `platform` (required): Platform name
- `metric_name` (required): Name of the metric

**Example:**
```
Show me the SQL for the uri_count metric
```

## Example Conversations with Gemini

### Example 1: Exploring Metrics

**User:** "What metrics are available for Firefox Desktop?"

**Gemini** (uses `list_metrics`): Shows all Firefox Desktop metrics grouped by category.

**User:** "Tell me more about the active_hours metric"

**Gemini** (uses `get_metric`): Shows detailed information including description, data source, and SQL expression.

### Example 2: Creating a New Metric

**User:** "I want to create a new metric to track daily active users"

**Gemini** (uses `generate_metric_template`): Generates a template with guidance.

**User:** "Here's my config: [shows TOML]"

**Gemini** (uses `validate_metric_config`): Validates and provides feedback.

### Example 3: Understanding Data Sources

**User:** "What data sources are available for Fenix?"

**Gemini** (uses `list_data_sources`): Lists all Fenix data sources.

**User:** "Show me details about baseline_clients_daily"

**Gemini** (uses `get_data_source`): Shows schema, columns, and configuration.

## Development

### Project Structure

```
mcp-server/
├── metric_hub_mcp/
│   ├── __init__.py
│   └── server.py          # Main MCP server implementation
├── tests/                 # Tests (coming soon)
├── pyproject.toml        # Project configuration
└── README.md             # This file
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy metric_hub_mcp/
```

## Architecture

The MCP server is built on:

- **MCP Protocol**: Standard protocol for AI-tool communication
- **mozilla-metric-config-parser**: Python SDK for metric-hub
- **ConfigCollection**: Loads and manages metric definitions from GitHub

The server loads metric configurations from the metric-hub GitHub repository and provides tools for querying and manipulating this data.

## Troubleshooting

### Server won't start

- Check Python version: `python3 --version` (must be 3.10+)
- Verify installation: `pip show metric-hub-mcp-server`
- Check dependencies: `pip install mozilla-metric-config-parser`

### Metrics not loading

- Ensure you have internet access (loads from GitHub)
- Check GitHub rate limits
- Try running: `python3 -c "from metric_config_parser.config import ConfigCollection; ConfigCollection.from_github_repo('https://github.com/mozilla/metric-hub')"`

### Validation errors

- Basic validation is performed by the MCP server
- For full validation (including SQL dry-run), use: `python3 .script/validate.py <file>`
- Ensure your GCP credentials are configured for BigQuery dry-run

## Contributing

Contributions are welcome! Please follow the existing code style and add tests for new features.

## License

MPL 2.0 - See the main metric-hub repository for details.

## Support

For issues and questions:
- File an issue in the metric-hub repository
- Contact the Data Engineering team at Mozilla
