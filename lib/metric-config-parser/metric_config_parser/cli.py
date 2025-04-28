"""CLI."""

import os
import sys
from pathlib import Path
from typing import Iterable

import click

from metric_config_parser.config import (
    DEFINITIONS_DIR,
    ConfigCollection,
    DefinitionConfig,
    Outcome,
    entity_from_path,
)
from metric_config_parser.function import FunctionsSpec

METRIC_HUB_REPO = "https://github.com/mozilla/metric-hub"


@click.group()
def cli():
    """Initialize CLI."""
    pass


@cli.command("validate")
@click.argument("path", type=click.Path(exists=True), nargs=-1)
@click.option(
    "--config_repos",
    "--config-repos",
    help="URLs to public repos with configs",
    multiple=True,
    default=[METRIC_HUB_REPO],
)
@click.option(
    "--private_config_repos",
    "--private-config-repos",
    help="URLs to private repos with configs",
    multiple=True,
)
def validate(path: Iterable[os.PathLike], config_repos, private_config_repos):
    """Validate config files."""
    dirty = False
    config_collection = ConfigCollection.from_github_repos(config_repos).from_github_repos(
        private_config_repos, is_private=True
    )

    # get updated definition files
    for config_file in path:
        config_file = Path(config_file)
        if not config_file.is_file():
            continue
        if ".example" in config_file.suffixes:
            print(f"Skipping example config {config_file}")
            continue

        if config_file.parent.name == DEFINITIONS_DIR:
            entity = entity_from_path(config_file)
            try:
                if isinstance(entity, Outcome):
                    entity.validate(config_collection)
                elif not isinstance(entity, FunctionsSpec):
                    entity.validate(config_collection, None)  # type: ignore
            except Exception as e:
                dirty = True
                print(e)
            else:
                print(f"{config_file} OK")

            if isinstance(entity, DefinitionConfig):
                config_collection.definitions.append(entity)

    for config_file in path:
        config_file = Path(config_file)
        if config_file.parent.name == DEFINITIONS_DIR:
            continue
        if not config_file.is_file():
            continue
        if ".example" in config_file.suffixes:
            print(f"Skipping example config {config_file}")
            continue
        print(f"Evaluating {config_file}...")
        entity = entity_from_path(config_file)
        try:
            if not isinstance(entity, FunctionsSpec) and not isinstance(entity, Outcome):
                entity.validate(config_collection, None)  # type: ignore
        except Exception as e:
            dirty = True
            print(e)
        else:
            print(f"{config_file} OK")

    sys.exit(1 if dirty else 0)
