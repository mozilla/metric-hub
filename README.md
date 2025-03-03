# metric-hub

metric-hub is the central source of truth for the definitions and metadata related to all of Mozilla's relevant business metrics. metric-hub is very much what is known as a ["semantic layer"](https://www.klipfolio.com/resources/data-stack/metrics-layer-vs-semantic-layer), in that the metric values themselves exist in the data warehouse, and the metric implementations exist in the data processing layer made of our [ETL infrastructure](https://github.com/mozilla/bigquery-etl/). metric-hub metric definitions can be thought of as pointers to the outputs of the canonical metric implementations, and it provides the abstraction layer that allows folks to access metric values without needing to know anything about the SQL required to extract those values from our warehouse.

Some metrics may only be needed within a limited context, such as a value to be tracked over the course of an experiment (handled by [jetstream](https://github.com/mozilla/jetstream), our automated experiment analysis framework), or a piece of data to be continuously monitored for one or more populations (via [OpMon](https://github.com/mozilla/opmon), an operational monitoring tool used to watch the impact of scaled roll-outs and to support certain product health dashboards). Other metrics are much more widely impactful, such as organizational KPIs and high level product success measurements.

For more information on how to add metric definitions please see the [docs on docs.telemetry.mozilla.org](https://docs.telemetry.mozilla.org/concepts/metric_hub.html)

All metric definitions can and should be referenced in other tooling and their configurations, including jetstream, OpMon, [BigQuery ETL](https://docs.telemetry.mozilla.org/concepts/metric_hub.html#using-metrics-in-etl-queries), and [Python scripts](https://docs.telemetry.mozilla.org/concepts/metric_hub.html#using-metrics-in-python-scripts). All metrics are also made available in auto-generated Looker Explores, from which visualizations and dashboards can be generated.

- **Jetstream** specific configs or defaults can be added in the `jetstream/` directory.
- **OpMon** specific configs or defaults can be added in the `opmon/` directory.
- **Looker Explore** specific configs or defaults can be added in the `looker/` directory. This directory also supports the definitions of "statistics" (i.e. specific aggregations of metric-hub metrics), which will be materialized as measures in the autogenerated Explores. How to do this is explained in detail in the [documentation](https://docs.telemetry.mozilla.org/concepts/metric_hub.html#using-metrics-in-looker).

Tool-specific configs take precedence over the metric definitions in the top level `definitions/` folder when used in the tooling, while in all other contexts `definitions/` is seen as the source of truth.


## Experiment Analysis Considerations

metric-hub's CI is configured to detect when a given change would affect experiment analysis, and to automatically rerun analysis for these experiments in certain scenarios. This behavior is not always desirable, and so it can also be overridden using `[ci rerun-skip]`. Continue reading to learn more about the automated rerun scenarios and when you may want to use `[ci rerun-skip]`.

### Automated Analysis Reruns

There are two main scenarios that trigger analysis reruns:

1. Changing default metrics (i.e., in `jetstream/defaults`)
    * this will trigger a rerun in the affected application of:
      * **all live** experiments
      * **completed** experiments that have **ended within the past 90 days**

2. Changing/Adding a custom experiment config file
    * this will trigger a rerun of the experiment with a slug matching the config file name, **even if the experiment already ended**

Scenario #1 in particular could come with significant cost, and is unlikely to be intended. Therefore, this is a good candidate for using `[ci rerun-skip]`, and should be the preferred approach for most changes.

Scenario #2 will also come with added cost, though less significant than Scenario #1. Whether using `[ci rerun-skip]` here is worthwhile will depend on a few factors. Here are a few examples of when to skip or not:
  * Skip
    * if you only care about changes going forward
      * Example: changes to weekly metrics before the first week of observation has elapsed
      * Example: add an experiment end date that is not in the past (e.g., to compute overall metrics before the experiment officially ends)
    * if the only thing changing is statistics (i.e., metrics themselves stay the same)
    * if you only care about one analysis window (e.g., overall)
  * Don't skip
    * if you want to rerun full (daily, weekly, overall) analysis anyway

And most importantly -- if you're not sure, you can always ask in `#ask-experimenter`!


### Manual Analysis Reruns
If you decide to use `[ci rerun-skip]` to prevent jetstream from automatically rerunning affected experiment analyses, your options will vary depending on whether the experiment(s) you care about are live or complete.

1. Live Experiments
    * Existing results will remain unchanged without manual intervention
    * Automated analysis for future daily runs will use the new configuration

2. Complete Experiments
    * Existing results will remain unchanged without manual intervention


The manual intervention mentioned above will require support from one of the DE/DS supporting Nimbus to run this manually, so reach out in `#ask-experimenter` to request support if needed. The supporting Nimbus team member will want to know:
* Experiment slug(s) (and Experimenter link(s) might be helpful)
* Analysis windows to run (daily, weekly, and/or overall)
* A link to the PR with the relevant configuration changes

After the manual analysis run is triggered, results availability will depend on numerous factors (number of metrics, population size, etc.), but usually can be expected within a few hours. If the experiment is complete, a Nimbus team member will need to refresh the results in Experimenter in order for the new results to display in the UI. If the experiment is live, Experimenter will automatically refresh the results (this job runs every 6 hours).
