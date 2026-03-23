FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY metric_hub_mcp/ metric_hub_mcp/

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["metric-hub-mcp-http"]
