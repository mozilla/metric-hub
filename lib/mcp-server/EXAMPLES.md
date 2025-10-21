# Metric Hub MCP Server - Usage Examples

This document provides practical examples of using the Metric Hub MCP server with AI assistants like Gemini.

## Table of Contents

1. [Exploring Metrics](#exploring-metrics)
2. [Creating New Metrics](#creating-new-metrics)
3. [Understanding Data Sources](#understanding-data-sources)
4. [Validating Configurations](#validating-configurations)
5. [Advanced Queries](#advanced-queries)

---

## Exploring Metrics

### Example 1: Discover Available Platforms

**User:** "What platforms are available in metric hub?"

**Expected AI Response:**
The AI will use `list_platforms` tool and respond with something like:

```
Metric Hub has the following platforms:

1. **firefox_desktop**
   - 150+ metrics
   - 25+ data sources

2. **fenix** (Firefox for Android)
   - 80+ metrics
   - 15+ data sources

3. **ads**
   - 10+ metrics
   - 5+ data sources

[... more platforms ...]
```

### Example 2: Browse Metrics by Category

**User:** "Show me all search-related metrics for Firefox Desktop"

**Expected AI Response:**
Uses `list_metrics` with platform="firefox_desktop" and category="search":

```
Firefox Desktop has 15 search-related metrics:

1. **search_count**
   - Friendly Name: SAP searches in Glean
   - Data Source: search_clients_engines_sources_daily
   - Description: Counts the number of searches a user performed through Firefox's Search Access Points...

2. **ad_click_rate**
   - Friendly Name: Ad Click Rate
   - Description: Total number of ad clicks over all clients divided by total SAP searches...

[... more metrics ...]
```

### Example 3: Get Detailed Metric Information

**User:** "Tell me everything about the active_hours metric"

**Expected AI Response:**
Uses `get_metric` with platform="firefox_desktop" and metric_name="active_hours":

```
# Metric: active_hours

**Platform:** firefox_desktop

**Friendly Name:** Active hours

## Description

Measures the amount of time (in 5-second increments) during which
Firefox received user input from a keyboard or mouse. The Firefox
window does not need to be focused.

**Category:** engagement
**Type:** scalar
**Data Source:** clients_daily

## Select Expression

```sql
{{agg_sum("active_hours_sum")}}
```

This metric aggregates the active_hours_sum field from the clients_daily table.
```

---

## Creating New Metrics

### Example 4: Generate a Simple Metric

**User:** "I want to create a metric that counts daily active users from the clients_daily table"

**Expected AI Response:**
Uses `generate_metric_template` with metric_type="simple":

```
Here's a template for your new metric:

```toml
[metrics.daily_active_users]
friendly_name = "Daily Active Users"
description = """
    Counts the number of unique clients who were active on a given day.
    This is based on the clients_daily table which contains one row per
    client per day.
"""
data_source = "clients_daily"
select_expression = 'COUNT(DISTINCT client_id)'
category = "engagement"
type = "scalar"
bigger_is_better = true
```

To use this metric:
1. Save it to definitions/firefox_desktop.toml
2. Validate using the validate_metric_config tool
3. Create a pull request
```

### Example 5: Create a Derived Metric

**User:** "How do I create a metric that calculates click-through rate from ad_clicks and ad_impressions?"

**Expected AI Response:**
Uses `generate_metric_template` with metric_type="derived":

```
For a derived metric like click-through rate, you should define it as:

```toml
[metrics.ad_click_through_rate]
friendly_name = "Ad Click Through Rate"
description = """
    The ratio of ad clicks to ad impressions. This is a derived metric
    that calculates clicks / impressions for each client.
"""
depends_on = ["ad_clicks", "ad_impressions"]

# In your experiment or monitoring config, define the computation:
[metrics.ad_click_through_rate.statistics.ratio]
numerator = "ad_clicks.sum"
denominator = "ad_impressions.sum"
```

This approach:
- Defines the metric's dependencies
- Defers the computation to the analysis stage
- Allows flexibility in how the ratio is calculated (per-client vs population)
```

---

## Understanding Data Sources

### Example 6: List Available Data Sources

**User:** "What data sources can I use for Firefox Desktop metrics?"

**Expected AI Response:**
Uses `list_data_sources` with platform="firefox_desktop":

```
Firefox Desktop has the following data sources:

## clients_daily
**From:** `mozdata.telemetry.clients_daily`
The main table for Firefox Desktop telemetry, containing one row per client per day.
**Experiments Column Type:** simple

## baseline_clients_daily
**From:** `mozdata.firefox_desktop.baseline_clients_daily`
Glean-based telemetry for Firefox Desktop.
**Experiments Column Type:** glean

## search_clients_engines_sources_daily
**From:** `mozdata.search.search_clients_engines_sources_daily`
Search activity aggregated by client, search engine, and source.

[... more data sources ...]
```

### Example 7: Get Data Source Details

**User:** "Show me the schema for clients_daily"

**Expected AI Response:**
Uses `get_data_source` with data_source_name="clients_daily":

```
# Data Source: clients_daily

**Platform:** firefox_desktop

**Friendly Name:** Clients Daily

## From Expression

```sql
mozdata.telemetry.clients_daily
```

## Configuration

- **Experiments Column Type:** simple
- **Client ID Column:** client_id
- **Submission Date Column:** submission_date
- **Analysis Units:** client_id
- **Columns as Dimensions:** true

This data source supports experiment analysis and includes all columns as
queryable dimensions in Looker.

Common columns include:
- client_id: Unique identifier for each client
- submission_date: Date of the data
- active_hours_sum: Total active hours
- uri_count: Number of URIs visited
- search_count: Number of searches performed
```

---

## Validating Configurations

### Example 8: Validate a Metric Definition

**User:** "Can you check if this metric config is valid?"

```toml
[metrics.test_metric]
friendly_name = "Test Metric"
data_source = "clients_daily"
select_expression = '{{agg_sum("active_hours_sum")}}'
```

**Expected AI Response:**
Uses `validate_metric_config`:

```
# Validation Results

✅ **Configuration is valid!**

⚠️ **Found 2 warning(s)**

## Warnings

- Metric 'test_metric': Missing 'description' (recommended)
- Metric 'test_metric': Missing 'category' (recommended)

Your configuration is structurally correct, but consider adding:
1. A detailed description explaining what this metric measures
2. A category (e.g., 'engagement', 'performance', 'search')

These fields help other developers understand and discover your metric.
```

### Example 9: Catch Configuration Errors

**User:** "Validate this config:"

```toml
[metrics.broken_metric]
friendly_name = "Broken"
select_expression = '{{agg_sum("field")}}'
```

**Expected AI Response:**
Uses `validate_metric_config`:

```
# Validation Results

❌ **Found 1 error(s)**

## Errors

- Metric 'broken_metric': 'data_source' is required when using 'select_expression'

⚠️ **Found 2 warning(s)**

## Warnings

- Metric 'broken_metric': Missing 'description' (recommended)
- Metric 'broken_metric': Missing 'category' (recommended)

Fix the error above before using this metric.
```

---

## Advanced Queries

### Example 10: Search Across All Metrics

**User:** "Find all metrics related to search counting"

**Expected AI Response:**
Uses `search_metrics` with query="search count":

```
# Search Results for 'search count'

**Found 8 metric(s)**

## search_count (firefox_desktop)
- **Match Type:** name
- **Friendly Name:** SAP searches in Glean
- **Description:** Counts the number of searches a user performed through Firefox's Search Access Points...

## search_count_glean (firefox_desktop)
- **Match Type:** name
- **Friendly Name:** SAP searches in Glean
- **Description:** Counts the number of searches in the Glean-based pipeline...

## tagged_search_count (firefox_desktop)
- **Match Type:** name
- **Friendly Name:** Tagged SAP searches
- **Description:** Counts searches submitted with a partner code...

[... more results ...]
```

### Example 11: Generate SQL for a Metric

**User:** "Show me the SQL query for the uri_count metric"

**Expected AI Response:**
Uses `get_metric_sql`:

```
# SQL for Metric: uri_count

## Select Expression

```sql
{{agg_sum("scalar_parent_browser_engagement_total_uri_count_sum")}}
```

## Data Source

**Name:** clients_daily

**From:**
```sql
mozdata.telemetry.clients_daily
```

## Full Query Example

```sql
SELECT
  client_id,
  submission_date,
  COALESCE(SUM(scalar_parent_browser_engagement_total_uri_count_sum), 0) AS uri_count
FROM
  mozdata.telemetry.clients_daily
WHERE
  submission_date >= '2025-01-01'
GROUP BY
  client_id,
  submission_date
```

This query:
1. Aggregates URI counts per client per day
2. Uses COALESCE to handle NULL values (returns 0 if no data)
3. Filters to recent data (adjust date as needed)
```

### Example 12: Multi-Step Workflow

**User:** "I need to create a new engagement metric for Firefox Desktop. Walk me through the process."

**Expected AI Response:**
Uses multiple tools in sequence:

```
I'll help you create a new engagement metric. Let's go step by step.

First, let me show you what data sources are available:

[Uses list_data_sources with platform="firefox_desktop"]

Great! For engagement metrics, clients_daily is typically the best choice.

Now, let's look at similar metrics to understand the pattern:

[Uses search_metrics with query="engagement"]

Based on these examples, here's a template for your new metric:

[Uses generate_metric_template]

```toml
[metrics.your_engagement_metric]
friendly_name = "Your Engagement Metric Name"
description = """
    Describe what this metric measures and how it reflects user engagement.
    Include details about:
    - What actions/behaviors are counted
    - How it's calculated
    - When to use this metric vs others
"""
data_source = "clients_daily"
select_expression = '{{agg_sum("your_field_name")}}'
category = "engagement"
type = "scalar"
bigger_is_better = true
owner = ["your-email@mozilla.org"]
```

Steps to complete:
1. Replace "your_field_name" with the actual column from clients_daily
2. Fill in the description
3. Set a meaningful friendly_name
4. Let me validate it once you're done!

What field from clients_daily do you want to aggregate?
```

---

## Tips for Using the MCP Server

1. **Be Specific:** When asking about metrics, include the platform name if known
2. **Iterative Refinement:** Start broad (list metrics) then drill down (get specific metric)
3. **Validate Early:** Use validation before committing to a metric design
4. **Search First:** Use search_metrics to find similar metrics before creating new ones
5. **Reference SQL:** Use get_metric_sql to understand how metrics are computed

## Common Patterns

### Pattern 1: Discover → Inspect → Create

```
User: "What metrics exist for search?" (search_metrics)
User: "Show me search_count details" (get_metric)
User: "Create a similar metric for ad searches" (generate_metric_template)
User: "Validate my new config" (validate_metric_config)
```

### Pattern 2: Data Source → Metric

```
User: "What data sources are available?" (list_data_sources)
User: "Show me clients_daily schema" (get_data_source)
User: "Create a metric using this data source" (generate_metric_template)
```

### Pattern 3: Platform → Category → Metric

```
User: "List platforms" (list_platforms)
User: "Show firefox_desktop performance metrics" (list_metrics with category)
User: "Tell me about uri_count" (get_metric)
User: "Show me the SQL" (get_metric_sql)
```
