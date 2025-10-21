#!/bin/bash
set -e

echo "Installing Metric Hub MCP Server..."
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo "Error: Python 3.10 or higher is required. You have Python $PYTHON_VERSION"
    exit 1
fi

echo "✓ Python version $PYTHON_VERSION is compatible"
echo ""

# Determine installation method
if [ -d "../../lib/metric-config-parser" ]; then
    echo "Found local metric-config-parser. Installing development version..."
    echo ""

    # Install local metric-config-parser
    echo "Installing metric-config-parser..."
    cd ../metric-config-parser
    pip install -e .
    cd ../mcp-server
    echo "✓ metric-config-parser installed"
    echo ""

    # Install MCP server in editable mode
    echo "Installing MCP server in editable mode..."
    pip install -e .
else
    echo "Installing from PyPI..."
    pip install .
fi

echo ""
echo "✓ Installation complete!"
echo ""
echo "Test the installation:"
echo "  metric-hub-mcp --help"
echo ""
echo "Or test loading configs:"
echo "  python3 -c 'from metric_config_parser.config import ConfigCollection; c = ConfigCollection.from_github_repo(\"https://github.com/mozilla/metric-hub\"); print(f\"Loaded {len(c.definitions)} platforms\")'"
