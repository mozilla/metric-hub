(
WITH clients_daily AS (
    SELECT
        client_id AS client_id,
        submission_date AS submission_date,
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
            ) AS clients_daily
        )

    GROUP BY
        client_id,
        submission_date
        )
SELECT
    clients_daily.client_id,
    clients_daily.submission_date,
    active_hours,
    
FROM
    clients_daily
)