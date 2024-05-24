(
    SELECT
        *
    FROM
(
            SELECT
                *
            FROM
                mozdata.telemetry.baseline
            WHERE
                submission_date = '2023-01-01'
            ) AS multiple_joined_baseline
        JOIN
    (
    SELECT
        *
    FROM
(
            SELECT
                *
            FROM
                mozdata.telemetry.baseline
            WHERE
                submission_date = '2023-01-01'
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
                submission_date = '2023-01-01'
            ) AS events
        )

    ON 
    joined_baseline.client_id = events.client_id
    
            )

    ON 
    multiple_joined_baseline.client_id =
        joined_baseline.client_id AND
        multiple_joined_baseline.submission_date =
        joined_baseline.submission_date
    
            )
