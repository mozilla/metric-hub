# Metric Hub MCP Server

The Metric Hub MCP server is deployed on Cloud Run. Connect your MCP client to the service URL — no local installation required.

## Client Configuration

### Claude CLI

```bash
claude mcp add --transport sse metric-hub https://metric-hub-mcp-744009727678.us-west1.run.app/sse
```

Or edit `~/.claude/mcp.json` manually:

```json
{
  "mcpServers": {
    "metric-hub": {
      "type": "claude mcp add --transport sse metric-hub https://metric-hub-mcp-744009727678.us-west1.run.app/sse",
      "url": "https://metric-hub-mcp-744009727678.us-west1.run.app/sse"
    }
  }
}
```

Verify with `claude mcp list`.

### Gemini CLI

```bash
gemini mcp add metric-hub https://metric-hub-mcp-744009727678.us-west1.run.app/sse
```

Or edit `~/.config/gemini-cli/settings.json` manually:

```json
{
  "mcpServers": {
    "metric-hub": {
      "url": "https://metric-hub-mcp-744009727678.us-west1.run.app/sse",
      "timeout": 30000
    }
  }
}
```

Verify the connection with `/mcp` — `metric-hub` should show as **CONNECTED**.

### Other MCP Clients

Connect to `https://metric-hub-mcp-744009727678.us-west1.run.app/sse` using SSE or streamable HTTP transport.

## Environment Variables (Cloud Run)

| Variable | Default | Description |
|---|---|---|
| `METRIC_HUB_REPO` | `https://github.com/mozilla/metric-hub` | Repository URL |
| `METRIC_HUB_BRANCH` | `main` | Branch to load |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Testing

```bash
npx @modelcontextprotocol/inspector https://metric-hub-mcp-744009727678.us-west1.run.app/sse
```

## Local Development

```bash
cd lib/mcp-server
pip install -e .
metric-hub-mcp  # starts stdio server
```
