(
    SELECT
        *
    FROM
(
            SELECT
                *
            FROM
                (SELECT 1)
            WHERE
                submission_date = '2023-01-01'
            ) AS main
        )
