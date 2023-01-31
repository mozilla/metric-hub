# metric-hub

Central hub for metric definitions that are considered the source of truth.
For more information on how to add metric definitions please see the [docs on docs.telemetry.mozilla.org](https://docs.telemetry.mozilla.org/concepts/metric_hub.html)

All metric definitions can be referenced in other tooling and their configurations, such as, [jetstream](https://github.com/mozilla/jetstream)
or [opmon](https://github.com/mozilla/opmon).

Jetstream specific configs or defaults can be added in the `jetstream/` directory.
OpMon specific configs or defaults can be added in the `opmon/` directory.

Tool-specific configs take precedence over the metric definitions in `definitions/` when used in the tooling, in all other contexts `definitions/` is seen as the source of truth.
