## metric-hub

Pre-defined dimensions for `{{ platform }}`. These dimensions are defined in [metric-hub](https://github.com/mozilla/metric-hub/blob/main/definitions/{{ platform }}.toml)

{% for dimension in dimensions["metric-hub"] %}
### {{ dimension.name }}

{% if dimension.friendly_name %}
**{{ dimension.friendly_name }}**
{% endif %}

{% if dimension.description -%}
{{ dimension.description | trim }}
{%- endif %}

Data Source: [`{{ dimension.data_source.name }}`](https://mozilla.github.io/metric-hub/data_sources/{{ platform }}/#{{ dimension.data_source.name }})

<details>
<summary>Definition:</summary>

```sql
{{ dimension.select_expression | trim }}
```
</details>

---

{% endfor %}

{% for repo, dimensions in dimensions.items() %}
{% if repo != "metric-hub" %}

## Overrides from {{ repo }}

Tool-specific configurations that override the defaults.
These dimensions are defined in [{{ repo }}](https://github.com/mozilla/{{ repo }}/blob/main/definitions/{{ platform }}.toml)

{% for dimension in dimensions %}
### {{ dimension.name }}

{% if dimension.friendly_name %}
**{{ dimension.friendly_name }}**
{% endif %}

{% if dimension.description -%}
{{ dimension.description | trim }}
{%- endif %}

Data Source: [`{{ dimension.data_source.name }}`](https://mozilla.github.io/metric-hub/data_sources/{{ platform }}/#{{ dimension.data_source.name }})

<details>
<summary>Definition:</summary>

```sql
{{ dimension.select_expression | trim }}
```
</details>

---

{% endfor %}

{% endif %}
{% endfor %}
