import copy
from typing import TYPE_CHECKING, Any, Mapping, Optional

import attr

if TYPE_CHECKING:
    from .config import ConfigCollection
    from .definition import DefinitionSpecSub, DefinitionSpec

from .data_source import DataSourcesSpec
from .experiment import Experiment, ExperimentConfiguration, ExperimentSpec
from .metric import MetricReference, MetricsConfigurationType, MetricsSpec
from .outcome import OutcomeSpec
from .parameter import ParameterDefinition, ParameterSpec
from .segment import SegmentsSpec
from .util import converter


@attr.s(auto_attribs=True)
class AnalysisConfiguration:
    """A fully concrete representation of the configuration for an experiment.

    Instead of instantiating this directly, consider using AnalysisSpec.resolve().
    """

    experiment: ExperimentConfiguration
    metrics: MetricsConfigurationType


@attr.s(auto_attribs=True)
class AnalysisSpec:
    """Represents a configuration file.

    The expected use is like:
        AnalysisSpec.from_dict(toml.load(my_configuration_file)).resolve(an_experimenter_object)
    which will produce a fully populated, concrete AnalysisConfiguration.
    """

    metrics: MetricsSpec = attr.Factory(MetricsSpec)
    data_sources: DataSourcesSpec = attr.Factory(DataSourcesSpec)
    segments: SegmentsSpec = attr.Factory(SegmentsSpec)
    parameters: ParameterSpec = attr.Factory(ParameterSpec)
    experiment: ExperimentSpec = attr.Factory(ExperimentSpec)
    _resolved: bool = False

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "AnalysisSpec":
        return converter.structure(d, cls)

    @classmethod
    def from_definition_spec(
        cls, spec: "DefinitionSpec", experiment: Optional["ExperimentSpec"] = None
    ) -> "AnalysisSpec":
        if experiment is None:
            return cls(
                metrics=spec.metrics,
                data_sources=spec.data_sources,
                segments=spec.segments,
                parameters=spec.parameters,
            )
        else:
            return cls(
                metrics=spec.metrics,
                data_sources=spec.data_sources,
                segments=spec.segments,
                parameters=spec.parameters,
                experiment=experiment,
            )

    @classmethod
    def default_for_experiment(
        cls, experiment: "Experiment", configs: "ConfigCollection"
    ) -> "AnalysisSpec":
        """Return the default spec based on the experiment type."""
        default_metrics = configs.get_platform_defaults(experiment.app_name)

        if default_metrics is None or not isinstance(default_metrics, AnalysisSpec):
            default_metrics = cls()

        type_metrics = configs.get_platform_defaults(experiment.type)

        if type_metrics is not None or not isinstance(default_metrics, AnalysisSpec):
            default_metrics.merge(type_metrics)

        return copy.deepcopy(default_metrics)

    def resolve(
        self,
        experiment: "Experiment",
        configs: "ConfigCollection",
    ) -> AnalysisConfiguration:
        if self._resolved:
            raise Exception("Can't resolve an AnalysisSpec twice")
        self._resolved = True

        for slug in experiment.outcomes:
            outcome = configs.spec_for_outcome(slug, experiment.app_name)

            if outcome is not None:
                self.merge_outcome(outcome)
            else:
                raise ValueError(
                    f"Outcome {slug} doesn't support the platform '{experiment.app_name}'"
                )

            self.merge_parameters(outcome.parameters)

        resolved_experiment = self.experiment.resolve(self, experiment, configs)
        metrics = self.metrics.resolve(self, resolved_experiment, configs)

        return AnalysisConfiguration(resolved_experiment, metrics)

    def merge(self, other: "DefinitionSpecSub"):
        """Merges another analysis spec into the current one."""
        if isinstance(other, AnalysisSpec):
            self.experiment.merge(other.experiment)
        self.metrics.merge(other.metrics)
        self.data_sources.merge(other.data_sources)
        if isinstance(other, AnalysisSpec) or hasattr(other, "segments"):
            self.segments.merge(other.segments)  # type: ignore

    def merge_outcome(self, other: "OutcomeSpec"):
        """Merges an outcome snippet into the analysis spec."""
        metrics = [MetricReference(metric_name) for metric_name, _ in other.metrics.items()]

        # metrics defined in outcome snippets are only computed for
        # weekly and overall analysis windows
        outcome_spec = MetricsSpec(
            daily=[],
            weekly=metrics,
            days28=[],
            overall=metrics,
            definitions=other.metrics,
        )
        outcome_spec.merge(self.metrics)
        other.data_sources.merge(self.data_sources)
        self.data_sources = other.data_sources
        self.metrics = outcome_spec

        if other.parameters:
            self.merge_parameters(other.parameters)

    @staticmethod
    def _merge_param(
        param_1: "ParameterDefinition", param_2: "ParameterDefinition"
    ) -> "ParameterDefinition":
        """
        Takes in two ParameterDefinitions and merges them together into
        a single ParameterDefinition.

        param_2 is used for setting default values if missing in param_1
        """

        default_value = param_1.default or param_2.default
        value = param_1.value or param_2.value or default_value

        final_value = (
            {**(default_value or dict()), **value}
            if isinstance(value, dict) and isinstance(default_value, dict)
            else value
        )

        return ParameterDefinition(
            **{
                "name": getattr(param_1, "name", None) or getattr(param_2, "name"),
                "friendly_name": getattr(param_1, "friendly_name", None)
                or getattr(param_2, "friendly_name"),
                "description": getattr(param_1, "description", None) or param_2.description,
                "value": (
                    {branch: branch_value for branch, branch_value in final_value.items()}
                    if isinstance(final_value, dict)
                    else final_value
                ),
                "default": getattr(param_1, "default", None)
                or default_value
                or (dict() if isinstance(final_value, dict) else None),
                "distinct_by_branch": getattr(param_1, "distinct_by_branch", None)
                or param_2.distinct_by_branch,
            }
        ).validate()

    def merge_parameters(self, other: "ParameterSpec") -> None:
        """
        Merges Outcome parameters with external config parameters.

        'self.parameters' -> contains custom config defined parameters
        'other' -> contains outcome defined
        """

        for param in other.definitions:
            external_config_param_settings = self.parameters.definitions.get(
                param, ParameterDefinition(name=param)
            )

            self.parameters.definitions[param] = AnalysisSpec._merge_param(
                external_config_param_settings, other.definitions[param]
            )
