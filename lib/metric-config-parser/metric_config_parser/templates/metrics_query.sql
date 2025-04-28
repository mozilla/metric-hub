{% include 'data_source_macros.j2' %}

(
{% for data_source_slug, data_source_info in metrics_per_data_source.items() -%}
{{ "WITH" if loop.first else "" }} {{ data_source_slug }} AS (
    SELECT
        {% if group_by_client_id -%}
        {{ data_source_info["data_source"].client_id_column }} AS client_id,
        {% endif -%}
        {% if group_by_submission_date -%}
        {{ data_source_info["data_source"].submission_date_column }} AS submission_date,
        {% endif -%}
        {% for dimension, dimension_sql in group_by.items() -%}
        {{ dimension_sql }} AS {{ dimension }},
        {% endfor -%}
        {% for metric in data_source_info["metrics"] -%}
        {{ metric.select_expression }} AS {{ metric.name }},
        {% endfor %}
    FROM {{ data_source_query(data_source_info["data_source"]) }}
    {% if group_by != {} or group_by_submission_date or group_by_client_id -%}
    GROUP BY
        {% for dimension, dimension_sql in group_by.items() -%}
        {{ dimension }}{{ "," if not loop.last or group_by_submission_date or group_by_client_id else "" }}
        {% endfor -%}
        {% if group_by_client_id -%}
        client_id{{ "," if group_by_submission_date else "" }}
        {% endif -%}
        {% if group_by_submission_date -%}
        submission_date
        {% endif -%}
    {% endif -%}
){{ "," if not loop.last else "" }}
{% endfor -%}

{% for data_source_slug, data_source_info in metrics_per_data_source.items() -%}
{% if loop.first -%}
SELECT
    {% if group_by_client_id -%}
    {{ metrics_per_data_source.keys() | first }}.client_id,
    {% endif -%}
    {% if group_by_submission_date -%}
    {{ metrics_per_data_source.keys() | first }}.submission_date,
    {% endif -%}
    {% for dimension, dimension_sql in group_by.items() -%}
    {{ metrics_per_data_source.keys() | first }}.{{ dimension }} AS {{ dimension }},
    {% endfor -%}
    {% for d, data_source_info in metrics_per_data_source.items() -%}
    {% for metric in data_source_info["metrics"] -%}
    {{ metric.name }},
    {% endfor -%}
    {% endfor %}
FROM
    {{ metrics_per_data_source.keys() | first }}
{% else -%}
    FULL OUTER JOIN {{ data_source_slug }}
    ON
        {% if group_by_submission_date -%}
        {{ data_source_slug }}.submission_date = {{ metrics_per_data_source.keys() | first }}.submission_date AND
        {% endif -%}
        {% if group_by_client_id -%}
        {{ data_source_slug }}.client_id = {{ metrics_per_data_source.keys() | first }}.client_id 
        {% endif -%}
        {% for dimension, dimension_sql in group_by.items() -%}
        AND {{ data_source_slug }}.{{ dimension }} = {{ metrics_per_data_source.keys() | first }}.{{ dimension }} 
        {% endfor -%}
{% endif -%}
{% endfor -%}
)