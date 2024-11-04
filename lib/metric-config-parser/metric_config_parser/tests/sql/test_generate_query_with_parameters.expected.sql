(
WITH clients_daily AS (
    SELECT
        client_id AS client_id,
        submission_date AS submission_date,
        build_id AS build_id,
        sample_id AS sample_id,
        COALESCE(SUM(active_hours_sum), 0) AS active_hours,
        COUNT(submission_date) AS days_of_use,
        
    FROM (
    SELECT
        *
    FROM
(
            SELECT
                *
            FROM
                mozdata.telemetry.clients_daily
            WHERE
                submission_date = '2023-01-01' AND normalized_channel = 'release'
            ) AS clients_daily
        )

    GROUP BY
        build_id,
        sample_id,
        client_id,
        submission_date
        )
SELECT
    clients_daily.client_id,
    clients_daily.submission_date,
    clients_daily.build_id AS build_id,
    clients_daily.sample_id AS sample_id,
    active_hours,
    days_of_use,
    
FROM
    clients_daily
)