Metrics and statistics that get computed for every `{{ platform }}` experiment.

{% for repo, default_config in default_config.items() %}

## {{ repo }}

[Source](https://github.com/mozilla/metric-hub/blob/main/defaults/{{ platform }}.toml)  |  [Edit](https://github.com/mozilla/metric-hub/edit/main/defaults/{{ platform }}.toml)

### Metrics

{% for metric in default_config["metrics"] %}

#### `{{ metric.name }}` 

{% if metric.friendly_name %}**{{ metric.friendly_name }}**{% endif %}

{% if metric.description -%}
{{ metric.description | trim }}
{%- endif %}

Analysis Periods: {% for period in default_config["metrics_analysis_periods"][metric.name] %} `{{ period }}` {% if not loop.last %}, {% endif %} {% endfor %}

Data Source: [`{{ metric.data_source.name }}`](#{{ metric.data_source.name }})

Statistics: {% for statistic in default_config["statistics"][metric.name] %}`{{ statistic }}`{% if not loop.last %}, {% endif %}{% endfor %}

<details>
<summary>Definition:</summary>

```sql
{{ metric.select_expression | trim }}
```
</details>


---
{% endfor %}

{% if data_sources %}
### Data Sources

{% for data_source in default_config["data_sources"] %}

#### [`{{ data_source.name }}` {%- if data_source.friendly_name -%}- {{ data_source.friendly_name }}{%- endif -%}](#{{ data_source.name }})

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

{% endfor %}