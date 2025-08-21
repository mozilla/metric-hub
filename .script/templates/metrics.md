## metric-hub

Pre-defined metrics for `{{ platform }}`. These metrics are defined in [metric-hub](https://github.com/mozilla/metric-hub/blob/main/definitions/{{ platform }}.toml)

{% for metric in metrics["metric-hub"] %}
### {{ metric.name }}

{% if metric.friendly_name %}
**{{ metric.friendly_name }}**
{% endif %}

{% if metric.description -%}
{{ metric.description | trim }}
{%- endif %}

Data Source: [`{{ metric.data_source.name }}`](https://mozilla.github.io/metric-hub/data_sources/{{ platform }}/#{{ metric.data_source.name }})

<details>
<summary>Definition:</summary>

```sql
SELECT
  {{ metric.select_expression | trim }}
FROM (
  {{ metric.data_source.from_expression | trim }}
)
```
</details>

{% for repo, metrics in metrics.items() %}
{% if repo != "metric-hub" and metric.name in metrics and metrics[metric.name].select_expression != metric.select_expression %}
**This metric has been overidden in {{ repo }}:**
<details>
<summary>Definition:</summary>

```sql
{{ metrics[metric.name].select_expression | trim }}
```
</details>
{% endif %}
{% endfor %}

---
{% endfor %}