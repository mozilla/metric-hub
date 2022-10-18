## metric-hub

Pre-defined segment data sources for `{{ platform }}`. These segment data sources are defined in [metric-hub](https://github.com/mozilla/metric-hub/blob/main/definitions/{{ platform }}.toml)

{% for data_source in data_sources["metric-hub"] %}
### [{{ data_source.name }}](#{{ data_source.name }})

Client ID column: `{{ data_source.client_id_column }}`

Submission Date column: ``{{ data_source.submission_date_column }}``

Window Start: `{{ data_source.window_start }}`

Window End: `{{ data_source.window_end}}`

{% if data_source.default_dataset %}
Default Dataset: [`{{ data_source.name }}`](https://mozilla.github.io/jetstream-config/data_sources/{{ platform }}/#{{ data_source.name }})
{% endif %}

<details>
<summary>Definition:</summary>

```sql
{{ data_source.from_expression | trim }}
```
</details>

---
{% endfor %}

{% for repo, data_sources in data_sources.items() %}
{% if repo != "metric-hub" %}

## Overrides from {{ repo }}

Tool-specific configurations that override the defaults.
These segment data sources are defined in [{{ repo }}](https://github.com/mozilla/{{ repo }}/blob/main/definitions/{{ platform }}.toml)

{% for data_source in data_sources %}
### [{{ data_source.name }}](#{{ data_source.name }})

Client ID column: `{{ data_source.client_id_column }}`

Submission Date column: ``{{ data_source.submission_date_column }}``

Window Start: `{{ data_source.window_start }}`

Window End: `{{ data_source.window_end}}`

{% if data_source.default_dataset %}
Default Dataset: [`{{ data_source.name }}`](https://mozilla.github.io/jetstream-config/data_sources/{{ platform }}/#{{ data_source.name }})
{% endif %}

<details>
<summary>Definition:</summary>

```sql
{{ data_source.from_expression | trim }}
```
</details>

---

{% endfor %}

{% endif %}
{% endfor %}