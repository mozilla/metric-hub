{% for metric in metrics %}
SELECT
    {{ data_sources[metric.data_source.name].submission_date_column }} AS submission_date,
    {{ data_sources[metric.data_source.name].client_id_column }} AS client_id,
    {{ metric.select_expression }} AS {{ metric.name }}
FROM
    {{ data_sources[metric.data_source.name].from_expr_for(None) }}
WHERE {{ data_sources[metric.data_source.name].submission_date_column }} = DATE('2020-01-01')
GROUP BY
    submission_date,
    client_id;
{% endfor %}

{% for segment in segments %}
SELECT
    {{ segment_data_sources[segment.data_source.name].submission_date_column }} AS submission_date,
    {{ segment_data_sources[segment.data_source.name].client_id_column }} AS client_id,
    {{ segment.select_expression }} AS {{ segment.name }}
FROM
    {{ segment_data_sources[segment.data_source.name].from_expression }}
WHERE {{ segment_data_sources[segment.data_source.name].submission_date_column }} = DATE('2020-01-01')
GROUP BY
    submission_date,
    client_id;
{% endfor %}

{% for dimension in dimensions %}
SELECT
    {{ dimension.select_expression }} AS {{ dimension.name }}
FROM
    {{ data_sources[dimension.data_source.name].from_expr_for(None) }}
WHERE {{ data_sources[dimension.data_source.name].submission_date_column }} = DATE('2020-01-01');
{% endfor %}

{% for metric in inflight %}
SELECT 
    {{ data_sources[metric.data_source.name].client_id_column }} AS client_id,
    MIN_BY({{ metric.select_expression }}, {{ data_sources[metric.data_source.name].timestamp_column }}) AS {{ metric.name }},
    MIN({{ data_sources[metric.data_source.name].timestamp_column }}) AS event_timestamp
FROM 
    {{ data_sources[metric.data_source.name].from_expr_for(None) }}
WHERE DATE({{ data_sources[metric.data_source.name].timestamp_column }}) = DATE('2024-01-01')
GROUP BY
    submission_date,
    client_id;
{% endfor %}    