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

{% for repo, dimensions in dimensions.items() %}
{% if repo != "metric-hub" and dimension.name in dimensions and dimensions[dimension.name].select_expression != dimension.select_expression %}
**This data source has been overidden in {{ repo }}:**
<details>
<summary>Definition:</summary>

```sql
{{ dimensions[dimension.name].select_expression | trim }}
```
</details>
{% endif %}
{% endfor %}

---

{% endfor %}
