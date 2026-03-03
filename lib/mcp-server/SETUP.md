# Metric Hub MCP Server

The Metric Hub MCP server is deployed on Cloud Run. Connect your MCP client to the service URL — no local installation required.

## Client Configuration

### Claude CLI

```bash
claude mcp add --transport http metric-hub https://<cloud-run-url>/mcp
```

Or edit `~/.claude/mcp.json` manually:

```json
{
  "mcpServers": {
    "metric-hub": {
      "type": "http",
      "url": "https://<cloud-run-url>/mcp"
    }
  }
}
```

Verify with `claude mcp list`.

### Gemini CLI

```bash
gemini mcp add metric-hub https://<cloud-run-url>/mcp
```

Or edit `~/.config/gemini-cli/settings.json` manually:

```json
{
  "mcpServers": {
    "metric-hub": {
      "url": "https://<cloud-run-url>/mcp",
      "timeout": 30000
    }
  }
}
```

Verify the connection with `/mcp` — `metric-hub` should show as **CONNECTED**.

### Other MCP Clients

Connect to `https://<cloud-run-url>/mcp` using SSE or streamable HTTP transport.

## Environment Variables (Cloud Run)

| Variable | Default | Description |
|---|---|---|
| `METRIC_HUB_REPO` | `https://github.com/mozilla/metric-hub` | Repository URL |
| `METRIC_HUB_BRANCH` | `main` | Branch to load |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Testing

```bash
npx @modelcontextprotocol/inspector https://<cloud-run-url>/mcp
```

## Local Development

```bash
cd lib/mcp-server
pip install -e .
metric-hub-mcp  # starts stdio server
```
