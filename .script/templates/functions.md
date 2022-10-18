{% for repo, functions in functions_repos.items() %}

## {{ repo }}

Pre-defined functions that can be used in select expressions across all metrics and segment definitions. These functions are defined in [{{ repo }}](https://github.com/mozilla/{{ repo }}/blob/main/definitions/functions.toml)

{% for function in functions %}
### {{ function.slug }}


{% if function.friendly_name %}
**{{ function.friendly_name }}**
{% endif %}

{% if function.description -%}
{{ function.description | trim }}
{%- endif %}

<details>
<summary>Definition:</summary>

```sql
{{ function.definition | trim }}
```
</details>

---

{% endfor %}
{% endfor %}