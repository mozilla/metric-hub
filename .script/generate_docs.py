"""Generates documentation for outcomes and default metrics and datasets."""

import shutil
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader
from metric_config_parser.analysis import AnalysisConfiguration, AnalysisSpec
from metric_config_parser.config import ConfigCollection
from metric_config_parser.definition import DefinitionSpec
from metric_config_parser.experiment import Experiment
from metric_config_parser.metric import AnalysisPeriod

ROOT = Path(__file__).parent.parent
DOCS_DIR = ROOT / ".docs"
TEMPLATES_DIR = Path(__file__).parent / "templates"
REPOS = {
    "metric-hub": ConfigCollection.from_github_repo(ROOT),
    "opmon-config": ConfigCollection.from_github_repo(
        "https://github.com/mozilla/metric-hub/tree/main/opmon"
    ),
    "jetstream-config": ConfigCollection.from_github_repo(
        "https://github.com/mozilla/metric-hub/tree/main/jetstream"
    ),
}

parser = ArgumentParser(description=__doc__)
parser.add_argument(
    "--output_dir",
    "--output-dir",
    required=True,
    help="Generated documentation is written to this output directory.",
)

_ConfigCollection = ConfigCollection.from_github_repos(
    [
        ROOT,
        "https://github.com/mozilla/metric-hub/tree/main/opmon",
        "https://github.com/mozilla/metric-hub/tree/main/jetstream",
    ]
)


def generate():
    """Runs the doc generation."""
    args = parser.parse_args()
    out_dir = Path(args.output_dir)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(DOCS_DIR, out_dir)

    generate_metrics_docs(out_dir / "docs")
    generate_data_source_docs(out_dir / "docs")
    generate_segment_data_sources_docs(out_dir / "docs")
    generate_segment_docs(out_dir / "docs")
    generate_outcome_docs(out_dir / "docs")
    generate_default_config_docs(out_dir / "docs")
    generate_function_docs(out_dir / "docs")
    generate_dimension_docs(out_dir / "docs")


@dataclass
class MinimalConfiguration:
    app_name: str


def generate_metrics_docs(out_dir: Path):
    """Generates docs for default metrics."""
    file_loader = FileSystemLoader(TEMPLATES_DIR)
    env = Environment(loader=file_loader)
    metrics_template = env.get_template("metrics.md")

    app_config = {}
    platform_definitions_repos = {repo: config for repo, config in REPOS.items()}

    for repo, config in platform_definitions_repos.items():
        for platform in config.definitions:
            cfg = MinimalConfiguration(platform.platform)
            metrics_list = []
            for _, metric in platform.spec.metrics.definitions.items():
                try:
                    ds_def = config.get_data_source_definition(
                        metric.data_source.name, platform.platform
                    )
                    metric.data_source = ds_def.resolve(platform.spec, cfg, configs=config)
                except Exception:
                    continue
                metrics_list.append(metric)
            if platform.platform not in app_config:
                app_config[platform.platform] = {repo: metrics_list}
            else:
                app_config[platform.platform][repo] = metrics_list

    for platform, metrics in app_config.items():
        metrics_doc = out_dir / "metrics" / (platform + ".md")
        metrics_doc.parent.mkdir(parents=True, exist_ok=True)
        metrics_doc.write_text(
            metrics_template.render(
                metrics=metrics,
                platform=platform,
            )
        )


def generate_data_source_docs(out_dir: Path):
    """Generates docs for default data sources."""
    file_loader = FileSystemLoader(TEMPLATES_DIR)
    env = Environment(loader=file_loader)
    data_sources_template = env.get_template("data_sources.md")

    app_config = {}
    platform_definitions_repos = {repo: config.definitions for repo, config in REPOS.items()}

    for repo, platform_definitions in platform_definitions_repos.items():
        for platform in platform_definitions:
            if platform.platform not in app_config:
                app_config[platform.platform] = {
                    repo: [
                        data_source
                        for _, data_source in platform.spec.data_sources.definitions.items()
                    ]
                }
            else:
                app_config[platform.platform][repo] = [
                    data_source for _, data_source in platform.spec.data_sources.definitions.items()
                ]

    for platform, data_sources in app_config.items():
        data_sources_doc = out_dir / "data_sources" / (platform + ".md")
        data_sources_doc.parent.mkdir(parents=True, exist_ok=True)
        data_sources_doc.write_text(
            data_sources_template.render(
                data_sources=data_sources,
                platform=platform,
            )
        )


def generate_segment_docs(out_dir: Path):
    """Generate docs for existing segments."""
    file_loader = FileSystemLoader(TEMPLATES_DIR)
    env = Environment(loader=file_loader)
    segments_template = env.get_template("segments.md")

    app_config = {}
    platform_definitions_repos = {repo: config.definitions for repo, config in REPOS.items()}

    for repo, platform_definitions in platform_definitions_repos.items():
        for platform in platform_definitions:
            if platform.platform not in app_config:
                app_config[platform.platform] = {
                    repo: [segment for _, segment in platform.spec.segments.definitions.items()]
                }
            else:
                app_config[platform.platform][repo] = [
                    segment for _, segment in platform.spec.segments.definitions.items()
                ]

    for platform, segments in app_config.items():
        if all([len(s) == 0 for _, s in segments.items()]):
            continue
        segments_doc = out_dir / "segments" / (platform + ".md")
        segments_doc.parent.mkdir(parents=True, exist_ok=True)
        segments_doc.write_text(
            segments_template.render(
                segments=segments,
                platform=platform,
            )
        )


def generate_segment_data_sources_docs(out_dir: Path):
    """Generate docs for existing segment data sources."""
    file_loader = FileSystemLoader(TEMPLATES_DIR)
    env = Environment(loader=file_loader)
    data_sources_template = env.get_template("segment_data_sources.md")

    app_config = {}
    platform_definitions_repos = {repo: config.definitions for repo, config in REPOS.items()}

    for repo, platform_definitions in platform_definitions_repos.items():
        for platform in platform_definitions:
            if platform.platform not in app_config:
                app_config[platform.platform] = {
                    repo: [segment for _, segment in platform.spec.segments.data_sources.items()]
                }
            else:
                app_config[platform.platform][repo] = [
                    segment for _, segment in platform.spec.segments.data_sources.items()
                ]

    for platform, data_sources in app_config.items():
        if all([len(s) == 0 for _, s in data_sources.items()]):
            continue
        data_sources_doc = out_dir / "segment_data_sources" / (platform + ".md")
        data_sources_doc.parent.mkdir(parents=True, exist_ok=True)
        data_sources_doc.write_text(
            data_sources_template.render(
                data_sources=data_sources,
                platform=platform,
            )
        )


def generate_dimension_docs(out_dir: Path):
    """Generate docs for existing dimensions."""
    file_loader = FileSystemLoader(TEMPLATES_DIR)
    env = Environment(loader=file_loader)
    dimensions_template = env.get_template("dimensions.md")

    app_config = {}
    platform_definitions_repos = {repo: config.definitions for repo, config in REPOS.items()}

    for repo, platform_definitions in platform_definitions_repos.items():
        for platform in platform_definitions:
            if platform.platform not in app_config:
                app_config[platform.platform] = {
                    repo: [
                        dimension for _, dimension in platform.spec.dimensions.definitions.items()
                    ]
                }
            else:
                app_config[platform.platform][repo] = [
                    dimension for _, dimension in platform.spec.dimensions.definitions.items()
                ]

    for platform, dimensions in app_config.items():
        if all([len(s) == 0 for _, s in dimensions.items()]):
            continue
        dimensions_doc = out_dir / "dimensions" / (platform + ".md")
        dimensions_doc.parent.mkdir(parents=True, exist_ok=True)
        dimensions_doc.write_text(
            dimensions_template.render(
                dimensions=dimensions,
                platform=platform,
            )
        )


def generate_outcome_docs(out_dir: Path):
    """Generates docs for existing outcomes."""
    file_loader = FileSystemLoader(TEMPLATES_DIR)
    env = Environment(loader=file_loader)
    outcome_template = env.get_template("outcome.md")

    for outcome in REPOS["jetstream-config"].outcomes:
        dummy_experiment = Experiment(
            experimenter_slug="dummy-experiment",
            normandy_slug="dummy_experiment",
            type="v6",
            status="Live",
            branches=[],
            end_date=None,
            reference_branch="control",
            is_high_population=False,
            start_date=datetime.now(),
            proposed_enrollment=14,
            app_name=outcome.platform,
        )

        spec = AnalysisSpec.from_dict({})
        spec.merge_outcome(outcome.spec)

        conf = spec.resolve(dummy_experiment, _ConfigCollection)

        default_metrics = [m.name for m in outcome.spec.default_metrics]
        summaries = [summary for summary in conf.metrics[AnalysisPeriod.OVERALL]]
        metrics = [
            summary.metric for summary in summaries if summary.metric.name not in default_metrics
        ]
        # deduplicate metrics
        deduplicated_metrics = []
        for metric in metrics:
            if metric not in deduplicated_metrics:
                deduplicated_metrics.append(metric)
        metrics = deduplicated_metrics

        # deduplicate data source objects by name, but keep the object
        data_sources = {}
        for m in metrics:
            if m.data_source is not None:
                data_sources[m.data_source.name] = m.data_source
        data_sources = list(data_sources.values())

        statistics_per_metric = {}
        for metric in metrics:
            statistics = [
                summary.statistic.name
                for summary in summaries
                if summary.metric.name == metric.name
            ]
            statistics_per_metric[metric.name] = statistics

        outcome_doc = out_dir / "outcomes" / outcome.platform / (outcome.slug + ".md")
        outcome_doc.parent.mkdir(parents=True, exist_ok=True)
        outcome_doc.write_text(
            outcome_template.render(
                slug=outcome.slug,
                platform=outcome.platform,
                outcome_name=outcome.spec.friendly_name,
                outcome_description=outcome.spec.description,
                metrics=metrics,
                data_sources=data_sources,
                statistics=statistics_per_metric,
            )
        )


def generate_default_config_docs(out_dir: Path):
    """Generates docs for default configs."""
    file_loader = FileSystemLoader(TEMPLATES_DIR)
    env = Environment(loader=file_loader)
    default_config_template = env.get_template("default_config.md")

    defaults_repos = {repo: config.defaults for repo, config in REPOS.items()}
    app_config = {}

    for repo, default_configs in defaults_repos.items():
        for platform_config in default_configs:
            dummy_experiment = Experiment(
                experimenter_slug="dummy-experiment",
                normandy_slug="dummy_experiment",
                type="v6",
                status="Live",
                branches=[],
                end_date=None,
                reference_branch="control",
                is_high_population=False,
                start_date=datetime.now(),
                proposed_enrollment=14,
                app_name=platform_config.slug,
            )

            spec = platform_config.spec
            conf = spec.resolve(dummy_experiment, _ConfigCollection)

            if isinstance(conf, AnalysisConfiguration):
                metric_summaries = [
                    summary for _, summaries in conf.metrics.items() for summary in summaries
                ]
            else:
                metric_summaries = [summary for summary in conf.metrics]

            metrics_analysis_periods = {}

            if isinstance(conf, AnalysisConfiguration):
                for period, summaries in conf.metrics.items():
                    for summary in summaries:
                        if summary.metric.name not in metrics_analysis_periods:
                            metrics_analysis_periods[summary.metric.name] = {
                                period.mozanalysis_label
                            }
                        else:
                            metrics_analysis_periods[summary.metric.name].add(
                                period.mozanalysis_label
                            )
            else:
                for summary in conf.metrics:
                    metrics_analysis_periods[summary.metric.name] = {
                        AnalysisPeriod.DAY.mozanalysis_label
                    }

            # deduplicate metrics
            metrics = []
            for metric in metric_summaries:
                if metric.metric not in metrics:
                    metrics.append(metric.metric)

            # deduplicate data source objects by name, but keep the object
            data_sources = {}
            for m in metrics:
                if m.data_source is not None:
                    data_sources[m.data_source.name] = m.data_source
            data_sources = list(data_sources.values())

            statistics_per_metric = {}
            for metric in metrics:
                statistics = [
                    summary.statistic.name
                    for summary in metric_summaries
                    if summary.metric.name == metric.name
                ]
                statistics_per_metric[metric.name] = set(statistics)

            if platform_config.slug not in app_config:
                app_config[platform_config.slug] = {
                    repo: {
                        "metrics": metrics,
                        "data_sources": data_sources,
                        "statistics": statistics_per_metric,
                        "metrics_analysis_periods": metrics_analysis_periods,
                    }
                }
            else:
                app_config[platform_config.slug][repo] = {
                    "metrics": metrics,
                    "data_sources": data_sources,
                    "statistics": statistics_per_metric,
                    "metrics_analysis_periods": metrics_analysis_periods,
                }

    for platform, default_config in app_config.items():
        default_config_doc = out_dir / "default_configs" / (platform + ".md")
        default_config_doc.parent.mkdir(parents=True, exist_ok=True)
        default_config_doc.write_text(
            default_config_template.render(
                platform=platform,
                default_config=default_config,
            )
        )


def generate_function_docs(out_dir):
    file_loader = FileSystemLoader(TEMPLATES_DIR)
    env = Environment(loader=file_loader)
    functions_template = env.get_template("functions.md")
    functions_repos = {
        repo: config.functions.functions.values()
        for repo, config in REPOS.items()
        if config.functions
    }

    functions_docs = out_dir / "functions.md"
    functions_docs.parent.mkdir(parents=True, exist_ok=True)
    functions_docs.write_text(functions_template.render(functions_repos=functions_repos))


if __name__ == "__main__":
    generate()
