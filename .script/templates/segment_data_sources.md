## metric-hub

Pre-defined segment data sources for `{{ platform }}`. These segment data sources are defined in [metric-hub](https://github.com/mozilla/metric-hub/blob/main/definitions/{{ platform }}.toml)

{% for data_source in data_sources["metric-hub"] %}
### [{{ data_source.name }}](#{{ data_source.name }})

Client ID column: `{{ data_source.client_id_column }}`

Submission Date column: ``{{ data_source.submission_date_column }}``

Window Start: `{{ data_source.window_start }}`

Window End: `{{ data_source.window_end}}`

{% if data_source.default_dataset %}
Default Dataset: [`{{ data_source.name }}`](https://mozilla.github.io/metric-hub/data_sources/{{ platform }}/#{{ data_source.name }})
{% endif %}

<details>
<summary>Definition:</summary>

```sql
{{ data_source.from_expression | trim }}
```
</details>

{% for repo, data_sources in data_sources.items() %}
{% if repo != "metric-hub" and data_source.name in data_sources and data_sources[data_source.name].from_expression != data_source.from_expression %}
**This data source has been overidden in {{ repo }}:**
<details>
<summary>Definition:</summary>

```sql
{{ data_sources[data_source.name].from_expression | trim }}
```
</details>
{% endif %}
{% endfor %}


---
{% endfor %}
