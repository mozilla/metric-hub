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
WITH enrollments AS (
    SELECT '00000' AS analysis_id,
        'test' AS branch,
        DATE('2020-01-01') AS enrollment_date,
        DATE('2020-01-01') AS exposure_date,
        1 AS num_enrollment_events,
        1 AS num_exposure_events
    UNION ALL
    SELECT '00000' AS analysis_id,
        'test' AS branch,
        DATE('2020-01-01') AS enrollment_date,
        DATE('2020-01-01') AS exposure_date,
        1 AS num_enrollment_events,
        1 AS num_exposure_events
)
SELECT
    {{ segment_data_sources[segment.data_source.name].submission_date_column }} AS submission_date,
    {{ segment_data_sources[segment.data_source.name].client_id_column }} AS client_id,
    {{ segment.select_expression }} AS {{ segment.name }}
FROM
    enrollments e
    LEFT JOIN {{ segment_data_sources[segment.data_source.name].from_expression }} s
        ON e.analysis_id = s.client_id
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
