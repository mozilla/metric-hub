(
WITH joined_baseline AS (
    SELECT
        client_id AS client_id,
        SELECT 1 AS joined_metric,
        
    FROM (
    SELECT
        *
    FROM
(
            SELECT
                *
            FROM
                mozdata.telemetry.baseline
            WHERE
                submission_date = '2023-01-01' AND normalized_channel = 'release'
            ) AS joined_baseline
        JOIN
    (
    SELECT
        *
    FROM
(
            SELECT
                *
            FROM
                mozdata.telemetry.events
            WHERE
                submission_date = '2023-01-01' AND normalized_channel = 'release'
            ) AS events
        )

    ON 
    joined_baseline.client_id = events.client_id
    
            )

    GROUP BY
        client_id
        )
SELECT
    joined_baseline.client_id,
    joined_metric,
    
FROM
    joined_baseline
)