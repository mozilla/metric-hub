# OpMon Config

Custom configs operational monitoring projects run via [opmon](https://github.com/mozilla/opmon).

## Adding Custom Configurations

Custom configuration files are written in [TOML](https://toml.io/en/).
More information on adding or changing configurations is available on [dtmo](https://docs.telemetry.mozilla.org/cookbooks/operational_monitoring.html).

To add or update a custom configuration, open a pull request.
CI checks will validate the columns, data sources, and SQL syntax.
Once CI completes and the PR has been automatically approved, you may merge the pull request, and OpMon will use the config to generate dashboard during its next nightly run.
Additional reviews by data scientists are necessary when making changes to [metric definitions considered as source of truth](https://github.com/mozilla/metric-hub/tree/main/definitions).
