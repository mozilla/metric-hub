# Metric Hub MCP Server

An MCP (Model Context Protocol) server for Mozilla Metric Hub that enables AI assistants like Claude to query, create, and validate metrics configurations.

## Features

### Metrics & Data Sources
- **Query Metrics**: Browse and search metrics across all platforms
- **Data Source Information**: Get details about available data sources
- **Validation**: Validate metric configurations before deployment
- **Templates**: Generate templates for creating new metrics
- **SQL Generation**: View generated SQL for metrics

### Experiments & Rollouts
- **Live Experiments**: Fetch current experiments and rollouts from Experimenter API
- **Experiment Details**: Get detailed information about specific experiments
- **Filter by Platform**: Filter experiments by application (firefox_desktop, fenix, etc.)
- **Status Tracking**: See which experiments are Live or Complete

### Configuration Management
- **Config Templates**: Generate templates for jetstream experiments, opmon monitoring, and looker dashboards
- **Create Configs**: Create new configuration files with optional base templates
- **List Configs**: Browse existing jetstream, opmon, and looker configurations
- **Get Config Contents**: View full configuration files

### Segments
- **List Segments**: Browse available user segments for analysis
- **Segment Details**: Get SQL expressions and configuration for specific segments

## Installation

### Prerequisites

- Python 3.10 or higher
- Access to the metric-hub repository

### Install from source

If you're working with the latest development version of metric-config-parser:

```bash
# First, install the local metric-config-parser
cd /metric-hub/lib/metric-config-parser
pip install -e .

# Then install the MCP server
cd /metric-hub/lib/mcp-server
pip install -e .
```

Or if you want to use the published version from PyPI:

```bash
cd /metric-hub/lib/mcp-server
pip install .
```

## Usage

### Setting Up with Claude Desktop/Code

The MCP server communicates via stdio and is designed to be used with Claude Desktop or Claude Code.

#### Step 1: Install the MCP Server

Follow the installation instructions above to install the server.

#### Step 2: Find Your Python Virtual Environment Path

If you installed using a virtual environment, you'll need the path to the Python executable:

```bash
# If using a venv in the project
which python  # or: which python3

# Example output: /metric-hub/lib/mcp-server/venv/bin/python
```

#### Step 3: Configure Claude

**For Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "metric-hub": {
      "command": "/path/to/your/venv/bin/python",
      "args": ["-m", "metric_hub_mcp.server"]
    }
  }
}
```

**For Claude Code** (`.claude/mcp.json` in your home directory or project):

```json
{
  "mcpServers": {
    "metric-hub": {
      "command": "/path/to/your/venv/bin/python",
      "args": ["-m", "metric_hub_mcp.server"]
    }
  }
}
```

#### Step 4: Restart Claude

- **Claude Desktop**: Quit and restart the application
- **Claude Code**: Restart the VS Code extension or reload the window

#### Step 5: Verify Connection

In Claude, try asking:
```
What platforms are available in metric-hub?
```

Claude should use the `list_platforms` tool to show you all available platforms.

### Alternative Configuration (Global Installation)

If you installed the package globally or in your system Python:

```json
{
  "mcpServers": {
    "metric-hub": {
      "command": "metric-hub-mcp"
    }
  }
}
```

### Running the Server Manually

You can also run the server manually for testing:

```bash
# Using the installed command
metric-hub-mcp

# Or using Python module directly
python -m metric_hub_mcp.server
```

The server will wait for JSON-RPC messages on stdin and respond on stdout.

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

### 10. `list_experiment_configs`

List configuration files from jetstream/, opmon/, or looker/ folders.

**Parameters:**
- `config_type` (required): Type of configs ('jetstream', 'opmon', or 'looker')

**Example:**
```
List all jetstream experiment configs
```

### 11. `get_experiment_config`

Get the contents of an existing configuration file.

**Parameters:**
- `config_type` (required): Type of config ('jetstream', 'opmon', or 'looker')
- `config_slug` (required): Config slug (filename without .toml extension)

**Example:**
```
Show me the jetstream config for my-experiment
```

### 12. `create_experiment_config`

Create a new configuration file in jetstream/, opmon/, or looker/ folder.

**Parameters:**
- `new_config_slug` (required): Slug for the new config
- `config_type` (required): Type of config ('jetstream', 'opmon', or 'looker')
- `base_config_slug` (optional): Existing config slug to copy from
- `config_content` (optional): TOML content for the new config

**Example:**
```
Create a new jetstream config called my-new-experiment based on existing-experiment
```

### 13. `generate_config_template`

Generate a template for a new configuration (jetstream experiment, opmon monitoring, or looker dashboard).

**Parameters:**
- `config_type` (required): Type of config ('jetstream', 'opmon', or 'looker')
- `template_type` (required): Template type (varies by config_type)
- `platform` (required): Platform name

**Template Types:**
- **jetstream**: 'basic', 'with_segments', 'with_custom_metrics', 'with_custom_data_source'
- **opmon**: 'basic', 'with_dimensions'
- **looker**: 'basic'

**Example:**
```
Generate a jetstream template with custom metrics for firefox_desktop
```

### 14. `list_segments`

List all segments for a specific platform.

**Parameters:**
- `platform` (required): Platform name

**Example:**
```
What segments are available for firefox_desktop?
```

### 15. `get_segment`

Get detailed information about a specific segment.

**Parameters:**
- `platform` (required): Platform name
- `segment_name` (required): Name of the segment

**Example:**
```
Show me details about the regular_users segment
```

### 16. `list_experiments`

List experiments and rollouts from the Experimenter API.

**Parameters:**
- `status` (optional): Filter by status ('Live' or 'Complete')
- `app_name` (optional): Filter by application name (e.g., 'firefox_desktop', 'fenix')
- `is_rollout` (optional): Filter to show only rollouts (true) or only experiments (false)

**Example:**
```
Show me all live experiments for firefox_desktop
```

### 17. `get_experiment`

Get detailed information about a specific experiment or rollout from Experimenter.

**Parameters:**
- `slug` (required): Experiment slug

**Example:**
```
Show me details about the experiment firefox-new-feature-test
```

## Example Conversations with Claude

### Example 1: Exploring Metrics

**User:** "What metrics are available for Firefox Desktop?"

**Claude** (uses `list_metrics`): Shows all Firefox Desktop metrics grouped by category.

**User:** "Tell me more about the active_hours metric"

**Claude** (uses `get_metric`): Shows detailed information including description, data source, and SQL expression.

### Example 2: Creating a New Metric

**User:** "I want to create a new metric to track daily active users"

**Claude** (uses `generate_metric_template`): Generates a template with guidance.

**User:** "Here's my config: [shows TOML]"

**Claude** (uses `validate_metric_config`): Validates and provides feedback.

### Example 3: Working with Experiments

**User:** "Show me all live experiments for Firefox Desktop"

**Claude** (uses `list_experiments`): Lists all live experiments filtered by platform.

**User:** "Tell me more about the experiment firefox-new-feature-test"

**Claude** (uses `get_experiment`): Shows detailed information including branches, dates, and whether configs exist in the repo.

**User:** "Create a new jetstream config for this experiment"

**Claude** (uses `generate_config_template` then `create_experiment_config`): Generates a template and creates the config file.

### Example 4: Understanding Data Sources and Segments

**User:** "What data sources are available for Fenix?"

**Claude** (uses `list_data_sources`): Lists all Fenix data sources.

**User:** "What segments can I use for analysis?"

**Claude** (uses `list_segments`): Shows all available segments for the platform.

**User:** "Show me details about the regular_users segment"

**Claude** (uses `get_segment`): Shows the segment's SQL expression and configuration.

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

### Claude can't find the MCP server

1. **Check your configuration file location:**
   - Claude Desktop: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Claude Code: `~/.claude/mcp.json` or `.claude/mcp.json` in your project

2. **Verify the Python path is correct:**
   ```bash
   # Find your Python executable
   which python3

   # Test if the module can be imported
   python3 -c "import metric_hub_mcp.server"
   ```

3. **Check the configuration syntax:**
   - Ensure the JSON is valid (use a JSON validator)
   - Use absolute paths, not relative paths
   - Example: `/metric-hub/lib/mcp-server/venv/bin/python3`

4. **Restart Claude:**
   - For Claude Desktop: Quit completely and restart
   - For Claude Code: Run "Reload Window" command in VS Code

5. **Check Claude's MCP logs:**
   - Claude Desktop: Check `~/Library/Logs/Claude/`
   - Claude Code: Check the Output panel for MCP-related messages

### Server won't start

- Check Python version: `python3 --version` (must be 3.10+)
- Verify installation: `pip show metric-hub-mcp-server`
- Check dependencies: `pip install mozilla-metric-config-parser`
- Test manually: `python3 -m metric_hub_mcp.server`

### Metrics not loading

- Ensure you have internet access (loads from GitHub)
- Check GitHub rate limits
- Try running: `python3 -c "from metric_config_parser.config import ConfigCollection; ConfigCollection.from_github_repo('https://github.com/mozilla/metric-hub')"`

### Experimenter API errors

- Check internet connectivity
- Verify access to `https://experimenter.services.mozilla.com/`
- The server will retry up to 3 times with 1-second delays between attempts

### Validation errors

- Basic validation is performed by the MCP server
- For full validation (including SQL dry-run), use: `python3 .script/validate.py <file>`
- Ensure your GCP credentials are configured for BigQuery dry-run

### Tools not appearing in Claude

- Make sure you restarted Claude after updating the config
- Check that the server is listed in Claude's settings/preferences
- Try asking Claude directly: "What MCP tools do you have access to?"
- Verify the server starts without errors: `python3 -m metric_hub_mcp.server` (should wait for input)

## Contributing

Contributions are welcome! Please follow the existing code style and add tests for new features.

## License

MPL 2.0 - See the main metric-hub repository for details.

## Support

For issues and questions:
- File an issue in the metric-hub repository
- Contact the Data Engineering team at Mozilla
