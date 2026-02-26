# Definitions

This directory contains definitions for specific metrics, data sources, dimensions or segments for the platform they target.
These definitions can be referenced in project specific configuration files without having to be redefined.

Metric definitions can be validated using the following Python script in Google Colab:

First, ensure that `mozanalysis` is available:

```shell
!pip install mozanalysis -qq
```

Second, setup the environment:

```python3
import pandas as pd

from google.cloud import bigquery
from google.colab import auth
from mozanalysis.config import ConfigLoader
from textwrap import dedent

auth.authenticate_user()

def fetch_metric_hub_definition(start_date, end_date, metric_slug, app_name, bq_project):
    start_date = pd.to_datetime(start_date).date()
    end_date = pd.to_datetime(end_date).date()

    # Set useful attributes based on the Metric Hub definition
    metric = ConfigLoader.get_metric(metric_slug=metric_slug, app_name=app_name)
    submission_date_column = metric.data_source.submission_date_column

    # Modify the metric source table string so that it formats nicely in the query.
    from_expression = metric.data_source._from_expr.replace("\n", "\n" + " " * 15)

    query = dedent(
        f"""
        SELECT {submission_date_column} AS submission_date,
               {metric.select_expr} AS value
          FROM {from_expression}
         WHERE {submission_date_column} BETWEEN '{start_date}' AND '{end_date}'
         GROUP BY {submission_date_column}
         ORDER BY 1
        """
    )

    print(
        "\n",
        "\n" + "-" * 110,
        "\n" + f" Querying for '{app_name}.{metric_slug}' ".center(110, "-"),
        f"\n> data_source: {metric.data_source.name}"
        f"\n{query}"
    )
    df = bigquery.Client(project=bq_project).query(query).to_dataframe()

    # ensure submission_date has type 'date'
    df[submission_date_column] = pd.to_datetime(df[submission_date_column]).dt.date

    return df
```

Third, verify that the relevant definitions can be queried.

```python3
bq_project = "moz-fx-data-bq-data-science"
start_date = "2024-03-14"
end_date = "2024-03-21"

# dictionary of {"app_name": ["list", "of", "metric", "slugs"]}
definitions = {
    "firefox_desktop": ["daily_active_users_v2", "desktop_dau_kpi_v2"],
    "multi_product": ["mobile_daily_active_users_v1", "mobile_dau_kpi_v1"],
    "fenix": ["daily_active_users_v2"],
    "firefox_ios": ["daily_active_users_v2"],
    "focus_android": ["daily_active_users_v2"],
    "focus_ios": ["daily_active_users_v2"],
}

for app_name, metric_slugs in definitions.items():
    for metric_slug in metric_slugs:
        df = fetch_metric_hub_definition(
            start_date=start_date,
            end_date=end_date,
            metric_slug=metric_slug,
            app_name=app_name,
            bq_project=bq_project,
        )
        display(df.set_index("submission_date").transpose())
```
