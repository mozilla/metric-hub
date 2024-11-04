(
WITH clients_daily AS (
    SELECT
        build_id AS build_id,
        COALESCE(SUM(active_hours_sum), 0) AS active_hours,
        
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
        build_id
        )
SELECT
    clients_daily.build_id AS build_id,
    active_hours,
    
FROM
    clients_daily
)