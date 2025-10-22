# Setup Guide for Metric Hub MCP Server

This guide will help you set up the Metric Hub MCP server for use with Gemini or other MCP clients.

## Quick Start

### 1. Install the Server

```bash
pip install -e .
```

### 2. Verify Installation

Check that the command is available in your PATH:

```bash
which metric-hub-mcp
```

Or on Windows:

```bash
where metric-hub-mcp
```

If the command is not found, you may need to add the pip install location to your PATH:

```bash
export PATH="$PATH:$HOME/.local/bin"
```

**Note:** MCP servers communicate via JSON-RPC over stdio and don't support traditional CLI arguments like `--help`. To test functionality, use one of the MCP clients (Claude Desktop, Gemini CLI) or the MCP Inspector tool (see Testing section below).

### 3. Test the Server

Test that the server can connect and load metrics:

```bash
python3 -c "from metric_config_parser.config import ConfigCollection; c = ConfigCollection.from_github_repo('https://github.com/mozilla/metric-hub'); print(f'Loaded {len(c.definitions)} platforms')"
```

## Configuration for Different MCP Clients

### Claude Desktop

1. Open the Claude Desktop config file:
   ```bash
   open ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

2. Add the metric-hub server:
   ```json
   {
     "mcpServers": {
       "metric-hub": {
         "command": "metric-hub-mcp"
       }
     }
   }
   ```

3. Restart Claude Desktop

4. Test by asking: "List all platforms in metric hub"

### Gemini CLI

Gemini CLI has full support for MCP servers. Follow these steps to add the Metric Hub server:

> **Quick Fix for "ModuleNotFoundError":** If you see errors like `ModuleNotFoundError: No module named 'mcp'` or `'toml'`, you need to use the virtual environment Python. Use the configuration in **Option 2** below with the full path to `venv/bin/python`.

#### Prerequisites

1. **Install Gemini CLI:**
   ```bash
   npm install -g @google/gemini-cli@latest
   ```

2. **Verify installation:**
   ```bash
   gemini --version
   ```

#### Option 1: Using the CLI Command (After Installation)

If you've installed the package with `pip install -e .`, add the server using:

```bash
gemini mcp add metric-hub metric-hub-mcp
```

This automatically configures the server in your settings.json file.

#### Option 1b: Using Virtual Environment Python (For Development - RECOMMENDED)

If you're developing locally with a virtual environment:

```bash
gemini mcp add metric-hub /metric-hub/lib/mcp-server/venv/bin/python -- -m metric_hub_mcp.server
```

Note: Adjust the path to match your actual project location.

#### Option 2: Manual Configuration

1. **Locate your settings file:**
   - macOS/Linux: `~/.config/gemini-cli/settings.json`
   - Windows: `%APPDATA%\gemini-cli\settings.json`

2. **Edit the settings file** to add the metric-hub server:

   **After installation:**
   ```json
   {
     "mcpServers": {
       "metric-hub": {
         "command": "metric-hub-mcp",
         "timeout": 30000,
         "trust": false
       }
     }
   }
   ```

   **For development (with virtual environment):**
   ```json
   {
     "mcpServers": {
       "metric-hub": {
         "command": "/metric-hub/lib/mcp-server/venv/bin/python",
         "args": ["-m", "metric_hub_mcp.server"],
         "cwd": "/metric-hub/lib/mcp-server",
         "timeout": 30000,
         "trust": false
       }
     }
   }
   ```

   **For development (without virtual environment):**
   ```json
   {
     "mcpServers": {
       "metric-hub": {
         "command": "python3",
         "args": ["-m", "metric_hub_mcp.server"],
         "cwd": "/metric-hub/lib/mcp-server",
         "env": {
           "PYTHONPATH": "/metric-hub/lib/mcp-server"
         },
         "timeout": 30000,
         "trust": false
       }
     }
   }
   ```

3. **Save the file** and restart Gemini CLI

#### Configuration Options

You can customize the server configuration with additional options:

**Full path (if not in PATH):**
```json
{
  "mcpServers": {
    "metric-hub": {
      "command": "/full/path/to/metric-hub-mcp"
    }
  }
}
```

**With environment variables:**
```json
{
  "mcpServers": {
    "metric-hub": {
      "command": "metric-hub-mcp",
      "env": {
        "METRIC_HUB_REPO": "https://github.com/mozilla/metric-hub",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Trusted mode (skip confirmations):**
```json
{
  "mcpServers": {
    "metric-hub": {
      "command": "metric-hub-mcp",
      "trust": true
    }
  }
}
```

#### Verify the Setup

1. **Start Gemini CLI:**
   ```bash
   gemini
   ```

2. **Check MCP server status:**
   ```
   /mcp
   ```

   You should see `metric-hub` listed with status "CONNECTED"

3. **Test the tools:**
   ```
   What platforms are available in metric hub?
   ```

#### Managing the Server

**List all configured servers:**
```bash
gemini mcp list
```

**Remove the server:**
```bash
gemini mcp remove metric-hub
```

**Manage authentication (if needed):**
```
/mcp auth metric-hub
```

### Other MCP Clients

For other MCP clients, configure them to run the `metric-hub-mcp` command using stdio protocol.

## Advanced Configuration

### Using a Local Metric Hub Repository

By default, the server loads metrics from the GitHub repository. To use a local copy:

1. Edit `metric_hub_mcp/server.py`
2. Find the `get_config_collection()` function
3. Change the configuration to use local path:

```python
def get_config_collection() -> ConfigCollection:
    """Get or initialize the config collection."""
    global _config_collection, _repo_path

    if _config_collection is None:
        # Use local repository
        _repo_path = Path("/metric-hub")

        logger.info(f"Loading metric hub configs from {_repo_path}")
        _config_collection = ConfigCollection.from_github_repo(
            "https://github.com/mozilla/metric-hub",
            # Optionally specify a different branch:
            # branch="your-branch-name"
        )

    return _config_collection
```

### Environment Variables

You can configure the server using environment variables:

```bash
# Set the metric hub repository URL
export METRIC_HUB_REPO="https://github.com/mozilla/metric-hub"

# Set the branch to use
export METRIC_HUB_BRANCH="main"

# Set log level
export LOG_LEVEL="DEBUG"
```

Then update the server code to read these variables:

```python
import os

repo_url = os.getenv("METRIC_HUB_REPO", "https://github.com/mozilla/metric-hub")
branch = os.getenv("METRIC_HUB_BRANCH", "main")
log_level = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(level=getattr(logging, log_level))
```

### Caching for Performance

To improve performance, you can enable caching:

```python
import functools

@functools.lru_cache(maxsize=1)
def get_config_collection() -> ConfigCollection:
    # ... existing code ...
```

This caches the config collection in memory.

## Troubleshooting

### Connection failed: MCP error -32000: Connection closed

**Problem:** Gemini CLI shows "Connection closed" error when trying to connect to the MCP server.

**Cause:** This usually means the Python process crashed on startup due to:
- Missing dependencies (mcp package not installed)
- Wrong Python interpreter (not using virtual environment)
- Import errors

**Solution:**

1. **Test the server manually:**
   ```bash
   cd /metric-hub/lib/mcp-server
   venv/bin/python -m metric_hub_mcp.server
   ```

   The server should start and wait for input. Press `Ctrl+C` to stop.

2. **Check dependencies are installed:**
   ```bash
   cd /metric-hub/lib/mcp-server
   source venv/bin/activate
   pip list | grep mcp
   ```

   You should see `mcp` in the output. If not, install dependencies:
   ```bash
   pip install -e .
   ```

3. **Update your Gemini CLI settings** to use the virtual environment Python:
   ```json
   {
     "mcpServers": {
       "metric-hub": {
         "command": "/metric-hub/lib/mcp-server/venv/bin/python",
         "args": ["-m", "metric_hub_mcp.server"],
         "cwd": "/metric-hub/lib/mcp-server"
       }
     }
   }
   ```

4. **Check the logs:**
   Look at Gemini CLI's stderr output for Python tracebacks that show the actual error.

### Command not found: metric-hub-mcp

**Problem:** The `metric-hub-mcp` command is not in your PATH.

**Solution:**
1. Find where pip installed it:
   ```bash
   pip show metric-hub-mcp-server
   ```

2. Add the scripts directory to your PATH:
   ```bash
   export PATH="$PATH:$HOME/.local/bin"
   ```

3. Or use the full path in your MCP client config:
   ```json
   {
     "command": "/full/path/to/metric-hub-mcp"
   }
   ```

### GitHub Rate Limiting

**Problem:** Server fails with GitHub rate limit errors.

**Solution:**
1. Authenticate with GitHub:
   ```bash
   git config --global credential.helper store
   ```

2. Or use a personal access token:
   ```bash
   export GITHUB_TOKEN="your_token_here"
   ```

3. Update the server to use the token:
   ```python
   _config_collection = ConfigCollection.from_github_repo(
       "https://github.com/mozilla/metric-hub",
       token=os.getenv("GITHUB_TOKEN")
   )
   ```

### Slow Loading

**Problem:** Server takes a long time to start.

**Solution:**
1. Use local repository instead of GitHub
2. Enable caching (see Advanced Configuration)
3. Pre-load configs at server startup

### Permission Errors

**Problem:** Permission denied when running the server.

**Solution:**
1. Install in user mode:
   ```bash
   pip install --user -e .
   ```

2. Or use a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

## Testing the Server

### Manual Testing

Test individual functions:

```bash
python3 << 'EOF'
import asyncio
from metric_hub_mcp.server import handle_list_platforms

async def test():
    result = await handle_list_platforms()
    print(result[0].text)

asyncio.run(test())
EOF
```

### Running Tests

```bash
cd mcp-server
pytest tests/ -v
```

### Testing with MCP Inspector

Use the MCP Inspector tool to test the server:

```bash
npx @modelcontextprotocol/inspector metric-hub-mcp
```

This opens a web interface where you can:
- See all available tools
- Test tool calls
- View server logs
- Debug issues

## Next Steps

Once the server is set up:

1. **Try example queries:**
   - "List all platforms in metric hub"
   - "Show me Firefox Desktop metrics"
   - "What is the active_hours metric?"

2. **Create new metrics:**
   - "Generate a template for a new metric"
   - "Validate this metric config"

3. **Explore data sources:**
   - "What data sources are available for Fenix?"
   - "Show me details about clients_daily"

## Getting Help

If you encounter issues:

1. Check the logs: The server logs to stderr
2. Enable debug logging: Set `LOG_LEVEL=DEBUG`
3. File an issue: https://github.com/mozilla/metric-hub/issues
4. Contact: fx-data-dev@mozilla.org
