# Metric Hub MCP Server

MCP server for Mozilla Metric Hub. Enables AI assistants to query metrics, data sources, segments, experiment configs, and live experiments from Experimenter.

See [SETUP.md](SETUP.md) for client configuration and deployment.

## Tools

| Tool | Description |
|---|---|
| `list_platforms` | List all platforms with metric definitions |
| `list_metrics` | List metrics for a platform (optional category filter) |
| `get_metric` | Get details for a specific metric |
| `search_metrics` | Search metrics by name/description across platforms |
| `get_metric_sql` | Get generated SQL for a metric |
| `list_data_sources` | List data sources for a platform |
| `get_data_source` | Get details for a specific data source |
| `list_segments` | List segments for a platform |
| `get_segment` | Get details for a specific segment |
| `generate_metric_template` | Generate a template for a new metric |
| `list_experiment_configs` | List jetstream/opmon/looker config files |
| `get_experiment_config` | Get contents of a config file |
| `create_experiment_config` | Create a new config file |
| `generate_config_template` | Generate a jetstream/opmon/looker template |
| `list_experiments` | List experiments from Experimenter API |
| `get_experiment` | Get details for a specific experiment |

## Development

```bash
cd lib/mcp-server
pip install -e .
pytest
ruff check .
```
