# metric-config-parser

This package parses configuration files that are compatible with [jetstream](https://github.com/mozilla/jetstream) and [opmon](https://github.com/mozilla/opmon) compatible configuration files.

## Installation

`pip install mozilla-metric-config-parser`

## Templating in `from_expression`

A data source's `from_expression` supports two independent templating layers:

* `{dataset}` (single braces, Python `str.format`) is replaced with an app-specific dataset
  for Glean apps. If used, `default_dataset` is mandatory.
* `{{experiment.<attr>}}` (double braces, Jinja) is replaced with an attribute of the
  experiment the data source is being resolved for, e.g. `{{experiment.normandy_slug}}`,
  `{{experiment.start_date_str}}`, `{{experiment.end_date_str}}`,
  `{{experiment.last_enrollment_date_str}}`. This is only rendered when the expression
  actually references `experiment`, and is only available when resolving a data source for
  an experiment.

```toml
[data_sources.messaging_events]
from_expression = """(
    SELECT *
    FROM `moz-fx-data-shared-prod.fenix.events_stream`
    WHERE STARTS_WITH(extras.string.message_key, '{{experiment.normandy_slug}}:')
)"""
experiments_column_type = "none"
```

A literal brace can still be written by doubling it, e.g. `'{{d10d0bf8-f5b5-c8b4-a8b2-2b9879e08c5d}}'`.

## Testing

### Pytest
```
pytest --ruff --ignore=metric_config_parser/tests/integration/
```

### Linting and formatting
```
ruff check metric_config_parser
ruff format --check metric_config_parser
mypy metric_config_parser
```