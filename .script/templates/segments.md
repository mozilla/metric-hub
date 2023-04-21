## metric-hub

Pre-defined segments for `{{ platform }}`. These segments are defined in [metric-hub](https://github.com/mozilla/metric-hub/blob/main/definitions/{{ platform }}.toml)

{% for segment in segments["metric-hub"] %}
### {{ segment.name }}

{% if segment.friendly_name %}
**{{ segment.friendly_name }}**
{% endif %}

{% if segment.description -%}
{{ segment.description | trim }}
{%- endif %}

Data Source: [`{{ segment.data_source.name }}`](https://mozilla.github.io/metric-hub/data_sources/{{ platform }}/#{{ segment.data_source.name }})

<details>
<summary>Definition:</summary>

```sql
{{ segment.select_expression | trim }}
```
</details>

{% for repo, segments in segments.items() %}
{% if repo != "metric-hub" and segment.name in segments and segments[segment.name].select_expression != segment.select_expression %}
**This segment has been overidden in {{ repo }}:**
<details>
<summary>Definition:</summary>

```sql
{{ segments[segment.name].select_expression | trim }}
```
</details>
{% endif %}
{% endfor %}

---

{% endfor %}
