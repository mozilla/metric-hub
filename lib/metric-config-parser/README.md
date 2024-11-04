# metric-config-parser

This package parses configuration files that are compatible with [jetstream](https://github.com/mozilla/jetstream) and [opmon](https://github.com/mozilla/opmon) compatible configuration files.

## Installation

`pip install mozilla-metric-config-parser`


## Testing

### Pytest
```
pytest --black --ignore=metric_config_parser/tests/integration/
```

### Linting and formatting
```
flake8 metric_config_parser
isort --check metric_config_parser
mypy metric_config_parser
```