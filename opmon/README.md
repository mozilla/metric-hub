# OpMon Config

> This is currently a WIP.
> We are moving [opmon-config](https://github.com/mozilla/opmon-config) into metric-hub. This is to improve the development experience when writing configs that depend on new or existing metrics.
> For now, keep adding configs to [opmon-config](https://github.com/mozilla/opmon-config)

Custom configs operational monitoring projects run via [opmon](https://github.com/mozilla/opmon).

## Adding Custom Configurations

Custom configuration files are written in [TOML](https://toml.io/en/).
More information on adding or changing configurations is available on [dtmo](https://docs.telemetry.mozilla.org/cookbooks/operational_monitoring.html).

To add or update a custom configuration, open a pull request.
CI checks will validate the columns, data sources, and SQL syntax.
