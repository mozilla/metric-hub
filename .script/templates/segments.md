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

Data Source: [`{{ segment.data_source.name }}`](https://mozilla.github.io/jetstream-config/data_sources/{{ platform }}/#{{ segment.data_source.name }})

<details>
<summary>Definition:</summary>

```sql
{{ segment.select_expression | trim }}
```
</details>

---

{% endfor %}

{% for repo, segments in segments.items() %}
{% if repo != "metric-hub" %}

## Overrides from {{ repo }}

Tool-specific configurations that override the defaults.
These segments are defined in [{{ repo }}](https://github.com/mozilla/{{ repo }}/blob/main/definitions/{{ platform }}.toml)

{% for segment in segments %}
### {{ segment.name }}

{% if segment.friendly_name %}
**{{ segment.friendly_name }}**
{% endif %}

{% if segment.description -%}
{{ segment.description | trim }}
{%- endif %}

Data Source: [`{{ segment.data_source.name }}`](https://mozilla.github.io/jetstream-config/data_sources/{{ platform }}/#{{ segment.data_source.name }})

<details>
<summary>Definition:</summary>

```sql
{{ segment.select_expression | trim }}
```
</details>

---

{% endfor %}

{% endif %}
{% endfor %}
