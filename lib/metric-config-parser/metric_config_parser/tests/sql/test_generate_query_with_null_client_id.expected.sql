(
WITH desktop_cohort_daily_retention AS (
    SELECT
        NULL AS client_id,
        submission_date AS submission_date,
        SUM(COALESCE(num_clients_in_cohort, 0)) AS cohort_clients_in_cohort,
        
    FROM (
    SELECT
        *
    FROM
(
            SELECT
                *
            FROM
                `moz-fx-data-shared-prod.telemetry.desktop_cohort_daily_retention`
            ) AS desktop_cohort_daily_retention
        )

    GROUP BY
        client_id,
        submission_date
        )
SELECT
    desktop_cohort_daily_retention.client_id,
    desktop_cohort_daily_retention.submission_date,
    cohort_clients_in_cohort,
    
FROM
    desktop_cohort_daily_retention
)