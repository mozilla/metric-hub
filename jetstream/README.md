# Jetstream Config

> This is currently a WIP.
> We are moving [jetstream-config](https://github.com/mozilla/jetstream-config) into metric-hub. This is to improve the development experience when writing experiment analysis configs that depend on new or existing metrics.
> For now, keep adding configs to [jetstream-config](https://github.com/mozilla/jetstream-config)

Custom configs for experiments and outcome snippets
analyzed in [jetstream](https://github.com/mozilla/jetstream).

## Adding Custom Configurations

Custom configuration files are written in [TOML](https://toml.io/en/).

To add or update a custom configuration, open a pull request.
CI checks will validate the columns, data sources, and SQL syntax.
Once CI completes, you may merge the pull request, which will trigger Jetstream to re-run your analysis.
No additional review is necessary to land configurations.
Are your analyses not rendering as expected? See https://experimenter.info/jetstream/troubleshooting.

Learn how to write a Jetstream configuration at <https://experimenter.info/jetstream/configuration>.

Learn more about Outcomes at <https://experimenter.info/jetstream/outcomes>.

See what outcomes and pre-defined metrics are available at https://mozilla.github.io/metric-hub
