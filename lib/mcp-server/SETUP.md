# Metric Hub MCP Server

The Metric Hub MCP server is deployed on Cloud Run. Connect your MCP client to the service URL — no local installation required.

The server exposes two transports:

- **Streamable HTTP** at `/mcp` — recommended. Stateless: works reliably on horizontally scaled backends.
- **SSE** at `/sse` (+ `/messages/`) — legacy, kept for older clients. Relies on per-instance session state and may fail on Cloud Run when consecutive requests are routed to different instances.

## Client Configuration

### Claude CLI

```bash
claude mcp add --transport http metric-hub https://metric-hub-mcp-744009727678.us-west1.run.app/mcp
```

Or edit `~/.claude/mcp.json` manually:

```json
{
  "mcpServers": {
    "metric-hub": {
      "type": "http",
      "url": "https://metric-hub-mcp-744009727678.us-west1.run.app/mcp"
    }
  }
}
```

Verify with `claude mcp list`.

### Gemini CLI

```bash
gemini mcp add metric-hub https://metric-hub-mcp-744009727678.us-west1.run.app/mcp
```

Or edit `~/.config/gemini-cli/settings.json` manually:

```json
{
  "mcpServers": {
    "metric-hub": {
      "url": "https://metric-hub-mcp-744009727678.us-west1.run.app/mcp",
      "timeout": 30000
    }
  }
}
```

Verify the connection with `/mcp` — `metric-hub` should show as **CONNECTED**.

### Other MCP Clients

Use streamable HTTP transport against `https://metric-hub-mcp-744009727678.us-west1.run.app/mcp`. The SSE endpoint at `/sse` is also available for older clients but is not recommended.

## Environment Variables (Cloud Run)

| Variable | Default | Description |
|---|---|---|
| `METRIC_HUB_REPO` | `https://github.com/mozilla/metric-hub` | Repository URL |
| `METRIC_HUB_BRANCH` | `main` | Branch to load |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Testing

```bash
npx @modelcontextprotocol/inspector https://metric-hub-mcp-744009727678.us-west1.run.app/mcp
```

## Local Development

```bash
cd lib/mcp-server
pip install -e .
metric-hub-mcp  # starts stdio server
```
