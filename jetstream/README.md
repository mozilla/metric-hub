# Jetstream Config

Custom configs for experiments and outcome snippets
analyzed in [jetstream](https://github.com/mozilla/jetstream).

## Adding Custom Configurations

Custom configuration files are written in [TOML](https://toml.io/en/).

To add or update a custom configuration, open a pull request.
CI checks will validate the columns, data sources, and SQL syntax.
Once CI completes and the PR has been automatically approved, you may merge the pull request, which will trigger Jetstream to re-run your analysis.
Additional reviews by data scientists are necessary when making changes to [metric definitions considered as source of truth](https://github.com/mozilla/metric-hub/tree/main/definitions).

Are your analyses not rendering as expected? See https://experimenter.info/deep-dives/jetstream/troubleshooting.

Learn how to write a Jetstream configuration at <https://experimenter.info/deep-dives/jetstream/configuration>.

Learn more about Outcomes at <https://experimenter.info/deep-dives/jetstream/outcomes>.

See what outcomes and pre-defined metrics are available at https://mozilla.github.io/metric-hub
