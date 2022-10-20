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
{{ metric.select_expression | trim }}
```
</details>

---

{% endfor %}

{% for repo, metrics in metrics.items() %}
{% if repo != "metric-hub" %}

## Overrides from {{ repo }}

Tool-specific configurations that override the defaults.
These metrics are defined in [{{ repo }}](https://github.com/mozilla/{{ repo }}/blob/main/definitions/{{ platform }}.toml)

{% for metric in metrics %}
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
{{ metric.select_expression | trim }}
```
</details>

---

{% endfor %}

{% endif %}
{% endfor %}