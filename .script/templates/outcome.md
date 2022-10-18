{% if outcome_description -%}
{{ outcome_description | trim }}
{% endif %}

[Source](https://github.com/mozilla/jetstream-config/blob/main/outcomes/{{ platform }}/{{ slug }}.toml)  |  [Edit](https://github.com/mozilla/jetstream-config/edit/main/outcomes/{{ platform }}/{{ slug }}.toml)


## Metrics

{% for metric in metrics %}

### `{{ metric.name }}` 

**{%- if metric.friendly_name -%}{{ metric.friendly_name }} {% endif %}**

{% if metric.description -%}
{{ metric.description | trim }}
{%- endif %}

Analysis Period: `weekly`, `overall`

Data Source: [`{{ metric.data_source.name }}`](#{{ metric.data_source.name }})

Statistics: {% for statistic in statistics[metric.name] %}`{{ statistic }}`{% if not loop.last %}, {% endif %}{% endfor %}

<details>
<summary>Definition:</summary>

```sql
{{ metric.select_expression | trim }}
```
</details>


---
{% endfor %}

{% if data_sources %}
## Data Sources

{% for data_source in data_sources %}

### [`{{ data_source.name }}` {%- if data_source.friendly_name -%}- {{ data_source.friendly_name }}{%- endif -%}](#{{ data_source.name }})

{% if data_source.description %}
{{ data_source.description | trim }}
{% endif %}

<details>
<summary>Definition:</summary>

```sql
{{ data_source._from_expr | trim }}
```
</details>

---
{% endfor %}
{% endif %}

