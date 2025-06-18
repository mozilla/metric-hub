"""
Dry run generated queries.

Passes all queries defined under sql/ to a Cloud Function that will run the
queries with the dry_run option enabled.

We could provision BigQuery credentials to the CircleCI job to allow it to run
the queries directly, but there is no way to restrict permissions such that
only dry runs can be performed. In order to reduce risk of CI or local users
accidentally running queries during tests, leaking and overwriting production
data, we proxy the queries through the dry run service endpoint.
"""

import json
import logging
import multiprocessing
import sys
from pathlib import Path
from typing import Any
import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.id_token import fetch_id_token
from urllib.request import Request, urlopen

import click
import requests
import requests.exceptions
from metric_config_parser.config import (
    DEFINITIONS_DIR,
    ConfigCollection,
    entity_from_path,
)
from metric_config_parser.function import FunctionsSpec

logger = logging.getLogger(__name__)


DRY_RUN_URL = "https://us-central1-moz-fx-data-shared-prod.cloudfunctions.net/bigquery-etl-dryrun"
FUNCTION_CONFIG = "functions.toml"
TEMPLATES_DIR = Path(__file__).parent / "templates"
NUM_QUERIES_PER_REQUEST = 1


@click.group()
def cli():
    """Initialize CLI."""
    pass


class DryRunFailedError(Exception):
    """Exception raised when dry run fails."""

    def __init__(self, error: Any, sql: str):
        """Initialize exception."""
        self.sql = sql
        super().__init__(error)


def dry_run_query(sql: str) -> None:
    """Dry run the provided SQL query."""
    try:
        auth_req = GoogleAuthRequest()
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(auth_req)
        if hasattr(creds, "id_token"):
            # Get token from default credentials for the current environment created via Cloud SDK run
            id_token = creds.id_token
        else:
            # If the environment variable GOOGLE_APPLICATION_CREDENTIALS is set to service account JSON file,
            # then ID token is acquired using this service account credentials.
            id_token = fetch_id_token(auth_req, DRY_RUN_URL)

        r = urlopen(
            Request(
                DRY_RUN_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {id_token}",
                },
                data=json.dumps(
                    {
                        "dataset": "mozanalysis",
                        "query": sql,
                    }
                ).encode("utf8"),
                method="POST",
            )
        )
        response = json.load(r)
    except Exception as e:
        # This may be a JSONDecode exception or something else.
        # If we got a HTTP exception, that's probably the most interesting thing to raise.
        try:
            r.raise_for_status()
        except requests.exceptions.RequestException as request_exception:
            e = request_exception
        except UnboundLocalError:
            pass
        raise DryRunFailedError(e, sql)

    if response["valid"]:
        logger.info("Dry run OK")
        return

    if "errors" in response and len(response["errors"]) == 1:
        error = response["errors"][0]
    else:
        error = None

    if (
        error
        and error.get("code", None) in [400, 403]
        and "does not have bigquery.tables.create permission for dataset"
        in error.get("message", "")
    ):
        # We want the dryrun service to only have read permissions, so
        # we expect CREATE VIEW and CREATE TABLE to throw specific
        # exceptions.
        logger.info("Dry run OK")
        return

    raise DryRunFailedError((error and error.get("message", None)) or response["errors"], sql=sql)


def _is_sql_valid(sql):
    try:
        dry_run_query(sql)
    except DryRunFailedError as e:
        print("Error evaluating SQL:")
        for i, line in enumerate(e.sql.split("\n")):
            print(f"{i + 1: 4d} {line.rstrip()}")
        print("")
        print(str(e))
        return False
    return True


@cli.command("validate")
@click.argument("path", type=click.Path(exists=True), nargs=-1)
@click.option(
    "--config_repos",
    "--config-repos",
    help="URLs to public repos with configs",
    multiple=True,
)
def validate(path, config_repos):
    """Validate config files."""
    dirty = False
    config_collection = ConfigCollection.from_github_repos(config_repos)

    # get updated function definitions
    for config_file in path:
        config_file = Path(config_file)
        if config_file.is_file() and config_file.name == FUNCTION_CONFIG:
            functions = entity_from_path(config_file)
            config_collection.functions = functions

    # get updated definition files
    for config_file in path:
        sql_to_validate = []
        config_file = Path(config_file)
        if not config_file.is_file():
            continue
        if ".example" in config_file.suffixes:
            print(f"Skipping example config {config_file}")
            continue

        if config_file.parent.name == DEFINITIONS_DIR:
            entity = entity_from_path(config_file)
            try:
                if not isinstance(entity, FunctionsSpec):
                    entity.validate(config_collection, None)
            except Exception as e:
                dirty = True
                print(e)
            else:
                if not isinstance(entity, FunctionsSpec):
                    validation_template = (Path(TEMPLATES_DIR) / "validation_query.sql").read_text()
                    env = config_collection.get_env().from_string(validation_template)

                    i = 0
                    progress = 0
                    metrics = []
                    data_sources = {}
                    for metric_name in entity.spec.metrics.definitions.keys():
                        i += 1
                        metric = config_collection.get_metric_definition(
                            metric_name, config_file.stem
                        )

                        if not metric:
                            print(f"Error with {metric_name}")
                            dirty = True
                            break

                        if metric.select_expression:
                            metric.select_expression = (
                                config_collection.get_env()
                                .from_string(metric.select_expression)
                                .render()
                            )
                            metrics.append(metric)

                        if metric.data_source:
                            data_source = config_collection.get_data_source_definition(
                                metric.data_source.name, config_file.stem
                            )
                            if metric.data_source.name not in data_sources:
                                data_sources[metric.data_source.name] = data_source

                        if (
                            i % NUM_QUERIES_PER_REQUEST == 0
                            or i == len(entity.spec.metrics.definitions.keys()) - 1
                        ):
                            sql = env.render(
                                metrics=metrics,
                                dimensions=[],
                                segments=[],
                                segment_data_sources=[],
                                data_sources={
                                    name: d.resolve(entity.spec, entity, config_collection)
                                    for name, d in data_sources.items()
                                },
                            )
                            if len(sql.strip()) > 0:
                                sql_to_validate.append(sql)
                                i = 0
                                metrics = []
                                progress += 1

                    segment_definitions = None
                    for (
                        segment_name,
                        segment,
                    ) in entity.spec.segments.definitions.items():
                        segment_definitions = entity.spec.segments.definitions

                        segment_definitions[segment_name].select_expression = (
                            config_collection.get_env()
                            .from_string(segment.select_expression)
                            .render()
                        )

                    if segment_definitions:
                        sql = env.render(
                            metrics=metrics,
                            dimensions=entity.spec.dimensions.definitions.values(),
                            segments=segment_definitions.values(),
                            segment_data_sources=entity.spec.segments.data_sources,
                            data_sources={
                                name: d.resolve(None, entity, config_collection)
                                for name, d in entity.spec.data_sources.definitions.items()
                            },
                        )
                        sql_to_validate.append(sql)

    print(f"Dry running {len(sql_to_validate)} SQL query batches")
    with multiprocessing.Pool(multiprocessing.cpu_count()) as p:
        result = p.map(_is_sql_valid, sql_to_validate, chunksize=1)
    if not all(result):
        sys.exit(1)
    print(f"{config_file} OK")

    sys.exit(1 if dirty else 0)


if __name__ == "__main__":
    validate()
