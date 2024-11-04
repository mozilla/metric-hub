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
        ),
 normandy_events AS (
    SELECT
        client_id AS client_id,
        submission_date AS submission_date,
        build_id AS build_id,
        sample_id AS sample_id,
        COALESCE(LOGICAL_OR(        event_category = 'normandy'
        AND event_method = 'unenroll'
        AND event_string_value = '{experiment_slug}'
     ), FALSE) AS unenroll,
        
    FROM (
    SELECT
        *
    FROM
(
            SELECT
                *
            FROM
                (
    SELECT
        *
    FROM mozdata.telemetry.events
    WHERE event_category = 'normandy'
)
            WHERE
                submission_date = '2023-01-01' AND normalized_channel = 'release'
            ) AS normandy_events
        )

    GROUP BY
        build_id,
        sample_id,
        client_id,
        submission_date
        ),
 events AS (
    SELECT
        client_id AS client_id,
        submission_date AS submission_date,
        build_id AS build_id,
        sample_id AS sample_id,
        COALESCE(LOGICAL_OR(            event_method = 'open_management'
            AND event_category = 'pwmgr'
         ), FALSE) AS view_about_logins,
        
    FROM (
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
    unenroll,
    view_about_logins,
    
FROM
    clients_daily
FULL OUTER JOIN normandy_events
    ON
        normandy_events.submission_date = clients_daily.submission_date AND
        normandy_events.client_id = clients_daily.client_id 
        AND normandy_events.build_id = clients_daily.build_id 
        AND normandy_events.sample_id = clients_daily.sample_id 
        FULL OUTER JOIN events
    ON
        events.submission_date = clients_daily.submission_date AND
        events.client_id = clients_daily.client_id 
        AND events.build_id = clients_daily.build_id 
        AND events.sample_id = clients_daily.sample_id 
        )