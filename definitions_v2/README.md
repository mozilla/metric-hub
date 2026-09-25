# definitions_v2: V2 metric definitions

This directory holds V2 metric definitions. A V2 metric is declarative. It names a data source, one
aggregation from a closed list, and the columns and conditions that aggregation reads. It contains
no SQL. Each consumer generates the SQL it needs from the same fields, so one definition serves both
Jetstream and Highwind.

V2 sits next to the V1 definitions in `definitions/`. Data sources, segments and V1 metrics stay in
`definitions/`. A V2 metric refers to a data source defined there.

See [example_config.toml.example](example_config.toml.example) for an annotated example that uses
every field.

## Files and layout

```
metric-hub/
  definitions/              V1 metrics and every data source
    firefox_desktop.toml
  definitions_v2/           V2 metrics
    firefox_desktop.toml
```

- One TOML file per application, named `<application>.toml`.
- The application comes from the file stem, as in `definitions/`. Do not put it inside the file.
- The only top-level table is `[metrics]`. Any other top-level key is rejected.
- Each metric is a table under `[metrics]`, keyed by the metric name.
- A metric lives in exactly one of `definitions/<application>.toml` or
  `definitions_v2/<application>.toml`. Defining the same name in both is an error.
- Porting a metric means deleting it from `definitions/` and adding it here, so the directory
  listing shows which metrics have moved.
- Data sources are not ported. They stay in `definitions/`, and both consumers read them as they do
  for V1 metrics.
- Files ending in `.example` are not loaded.

metric-config-parser loads these files with their own schema and validation. They are not read by
the V1 parser.

## Field reference

The table key is the metric name. The parser does not restrict it beyond TOML key syntax. Use
lowercase snake_case, as in `definitions/`.

| field | type | required | default | meaning |
| --- | --- | --- | --- | --- |
| `data_source` | string | yes | | Name of a data source defined in `definitions/<application>.toml`. |
| `aggregation` | string | yes | | One of `sum`, `count`, `count_where`, `any`, `recency_within`. Decides how a unit's rows become one value. |
| `column` | string | see below | | A plain column name on the data source. |
| `where` | list of conditions | see below | empty | Row conditions for `count_where` and `any`. |
| `within_days` | integer | `recency_within` only | | Number of days for `recency_within`. |
| `threshold` | `{ op, value }` | no | | Compares the aggregated value and turns it into 0/1. |
| `scale` | number | no | | Multiplies the final value. |
| `cumulative_window` | integer (days) | no | | Length of the cumulative windows Highwind computes. |
| `incremental_window` | integer (days) | no | | Length of the incremental windows Highwind computes. |
| `repeat_windows` | boolean | no | `false` | Whether the windows repeat for the length of the experiment. |
| `statistics` | table of tables | no | | Statistics for the metric. |
| `friendly_name` | string | no | | Display name on the results page. |
| `description` | string | no | | Display description on the results page. |
| `bigger_is_better` | boolean | no | `true` | Direction of improvement on the results page. |

Which of `column`, `where` and `within_days` are required depends on the aggregation:

| aggregation | `column` | `where` | `within_days` |
| --- | --- | --- | --- |
| `sum` | required | not allowed | not allowed |
| `count` | required | not allowed | not allowed |
| `recency_within` | required | not allowed | required |
| `count_where` | exactly one of `column` or `where` | exactly one of `column` or `where` | not allowed |
| `any` | exactly one of `column` or `where` | exactly one of `column` or `where` | not allowed |

A column name must match `^[A-Za-z_][A-Za-z0-9_]*$`. It is a name, never an expression, so
`COALESCE(x, 0)`, `a.b` and `x > 0` are all rejected.

No field takes SQL. There is no `select_expression`. Any key not listed above is rejected.

## Aggregations

A unit is whatever the analysis counts: a client, or a profile group. Each aggregation reduces a
unit's rows in one window to one value.

### `sum`

The sum of `column` over the unit's rows. Null values are ignored. A unit with no rows, or with only
null values, gets 0. The result is a number.

```toml
[metrics.active_hours]
data_source = "clients_daily"
aggregation = "sum"
column = "active_hours_sum"
```

### `count`

The number of rows where `column` is not null. A unit with no rows gets 0. The result is a count.

```toml
[metrics.days_of_use]
data_source = "clients_daily"
aggregation = "count"
column = "submission_date"
```

### `count_where`

The number of rows where every condition holds. A row where a condition evaluates to null does not
match. A unit with no rows gets 0. The result is a count.

```toml
[metrics.qualified_cumulative_days_of_use]
data_source = "clients_daily"
aggregation = "count_where"

[[metrics.qualified_cumulative_days_of_use.where]]
column = "active_hours_sum"
op = ">"
value = 0

[[metrics.qualified_cumulative_days_of_use.where]]
column = "scalar_parent_browser_engagement_total_uri_count_normal_and_private_mode_sum"
op = ">"
value = 0
```

### `any`

1 if at least one row matches every condition, otherwise 0. A unit with no rows gets 0. The result
is 0/1.

```toml
[metrics.is_default_browser]
data_source = "clients_daily"
aggregation = "any"
column = "is_default_browser"
```

### `recency_within`

1 if the unit was active within the last `within_days` days, otherwise 0. `column` must be a
28-day activity bit pattern such as `days_active_bits`, where each row records the days the unit was
active in the 28 days up to and including that row's date.

Each row is decoded to the number of days since the most recent active day, where 0 means active on
the row's own date. The unit's value is the smallest of these over its rows in the window. A unit
with no rows, or with no active days recorded, gets 30, which is outside the 28-day range. The
result is 1 when that value is less than `within_days`, so `within_days = 3` means active on the
row's date or one of the two days before it. The result is 0/1.

The decoding, the comparison and the value for a unit with no rows are fixed. The author supplies
only the column and the number of days.

```toml
[metrics.active_in_last_3_days_legacy]
data_source = "firefox_desktop_active_users_view"
aggregation = "recency_within"
column = "days_active_bits"
within_days = 3
```

## Conditions

`where` is a list of conditions. A row matches when every condition holds. There is no OR.

Each condition is a table with these keys:

| key | required | meaning |
| --- | --- | --- |
| `column` | yes | A plain column name. |
| `op` | no | One of the operators below. Leave it out to test a boolean column for true. |
| `value` | with a comparison operator | The value to compare against. |

Operators:

| op | matches when | `value` |
| --- | --- | --- |
| `>` | column is greater than value | required |
| `>=` | column is greater than or equal to value | required |
| `<` | column is less than value | required |
| `<=` | column is less than or equal to value | required |
| `=` | column equals value | required |
| `!=` | column does not equal value | required |
| `IS NULL` | column is null | not allowed |
| `IS NOT NULL` | column is not null | not allowed |
| (no `op`) | column is true | not allowed |

`value` is a number, string or boolean. The parser checks that it is present when the operator
needs it, and absent otherwise. It does not check its type.

Null handling: a comparison against a null column does not match. This includes `!=`, so
`column != 0` does not match rows where the column is null. The boolean form matches only true, not
false or null. Use `IS NULL` or `IS NOT NULL` to test for null.

There is no IN, NOT, LIKE, function call or expression.

```toml
[[metrics.release_days_with_search_engine.where]]
column = "normalized_channel"
op = "="
value = "release"

[[metrics.release_days_with_search_engine.where]]
column = "default_search_engine"
op = "IS NOT NULL"
```

### The `column` shorthand

On `count_where` and `any`, `column = "x"` is the same as a single condition testing the boolean
column `x` for true. A metric gives either `column` or `where`, not both.

```toml
[metrics.is_default_browser]
data_source = "clients_daily"
aggregation = "any"
column = "is_default_browser"
```

is the same as:

```toml
[metrics.is_default_browser]
data_source = "clients_daily"
aggregation = "any"

[[metrics.is_default_browser.where]]
column = "is_default_browser"
```

## Threshold and scale

Both apply once, to the aggregated value for a window. They do not apply per row.

`threshold` compares the aggregated value with a number. The result is 1 when the comparison holds
and 0 otherwise, so a metric with a threshold is 0/1. `op` must be one of `>`, `>=`, `<`, `<=`,
`=`, `!=`, and `value` must be a number.

```toml
[metrics.retained]
data_source = "clients_daily"
aggregation = "sum"
column = "pings_aggregated_by_this_row"
threshold = { op = ">", value = 0 }
```

`scale` multiplies the final value by a number. When both are set, the threshold is applied first
and the scale second, so the result is 0 or the scale.

```toml
[metrics.default_browser_per_1000]
data_source = "clients_daily"
aggregation = "count_where"
column = "is_default_browser"
scale = 1000
```

## Windows

Three fields say which windows Highwind computes for the metric. Lengths are in days, counted from
each unit's enrollment. Day 0 is the enrollment day.

- `cumulative_window = N`: windows that start at day 0. Each covers everything from enrollment to the
  end of the window.
- `incremental_window = N`: back-to-back windows of N days, starting at day 0. Each covers only its
  own days, with nothing carried forward from earlier windows.
- `repeat_windows`: when `false`, each family set produces one window, the first N days. When
  `true`, the windows continue for as long as the experiment runs.

Leave a length out to skip that family. A metric with neither length is valid, and Highwind does not
compute it. `repeat_windows = true` requires at least one length.

Highwind produces a window only once it is complete, that is, once all of its days have data.

Windows each setting produces, for an experiment observed for 21 days:

| setting | windows (days, end exclusive) |
| --- | --- |
| `cumulative_window = 7`, `repeat_windows = true` | [0,7) [0,14) [0,21) |
| `incremental_window = 7`, `repeat_windows = true` | [0,7) [7,14) [14,21) |
| `cumulative_window = 3` | [0,3) |
| `incremental_window = 7` | [0,7) |
| `cumulative_window = 7`, `incremental_window = 7`, `repeat_windows = true` | cumulative [0,7) [0,14) [0,21), incremental [0,7) [7,14) [14,21) |

A metric has one length per family. Two one-off windows of different lengths, such as 3-day and
7-day retention, are two metrics.

0/1 metrics such as `retained` usually use incremental windows. Over a growing cumulative window
nearly every unit reaches 1.

Highwind builds all the windows in one analysis from one grid of equal-length buckets. The window
lengths used together in one analysis must fit a common grid. The schema does not check this. How
lengths that do not fit are handled is decided by Highwind.

Jetstream does not read the window fields. Its analysis windows are configured in
`jetstream/defaults/`.

## Statistics

`statistics` is a table of tables. Each key is a statistic name and its table holds that
statistic's parameters. An empty table means no parameters.

```toml
[metrics.active_hours.statistics.bootstrap_mean]

[metrics.active_hours.statistics.deciles]
```

Nothing reads this field yet. Jetstream takes statistics from `jetstream/defaults/`. The parser
checks only the shape, not the statistic names.

## Validation

metric-config-parser loads every file in `definitions_v2/` when it loads the repository, and fails
to load if any of the following holds.

File and keys:

- The file has a top-level key other than `metrics`.
- A metric, condition or threshold has a key not listed in this document.
- A metric has no `data_source` or no `aggregation`.
- A condition has no `column`, or a threshold is missing `op` or `value`.

Fields:

- `aggregation` is not one of the five.
- `sum`, `count` or `recency_within` has no `column`, or has `where`.
- `count_where` or `any` has both `column` and `where`, or neither.
- `recency_within` has no `within_days`, or `within_days` is not a positive integer.
- `within_days` is set on any other aggregation.
- A `column`, or a condition's `column`, is not a plain column name.
- A condition's `op` is not one of the listed operators.
- A comparison operator has no `value`, or `IS NULL`, `IS NOT NULL` or the boolean form has one.
- `threshold.op` is not a comparison operator, or `threshold.value` is not a number.
- `scale` is not a number.
- `cumulative_window` or `incremental_window` is set and is not a positive integer.
- `repeat_windows` is not a boolean, or is `true` with neither window length set.
- `statistics` is not a table of tables.

Booleans are not accepted where a number or integer is required.

Across files:

- `data_source` does not name a data source in `definitions/<application>.toml` for the same
  application.
- The metric name is also defined in `definitions/<application>.toml`.

Not checked:

- Whether a column exists on the data source. The parser has no table schemas.
- Whether window lengths used together fit a common grid.
- Statistic names, and the types of `friendly_name`, `description` and `bigger_is_better`.

## How consumers use a V2 metric (planned)

This section describes behaviour that is not implemented yet. Nothing reads V2 definitions today.

Both consumers generate SQL from the same fields. In the tables below, `c` is `column` and `p` is
the conditions joined with AND (the `column` shorthand is the condition `c`).

### Jetstream

metric-config-parser builds a V1 metric definition from the V2 fields, so Jetstream reads it like
any other metric. The definition carries the name, the data source, a generated
`select_expression`, and `friendly_name`, `description` and `bigger_is_better`. The window fields
and `statistics` are not passed through.

| aggregation | `select_expression` |
| --- | --- |
| `sum` | `COALESCE(SUM(c), 0)` |
| `count` | `COUNT(c)` |
| `count_where` | `COUNTIF(p)` |
| `any` | `COALESCE(LOGICAL_OR(p), FALSE)` |
| `recency_within` N | `COALESCE(MIN(mozfun.bits28.days_since_seen(c)), 30) < N` |
| with `threshold` | `<expression> <op> <value>` |
| with `scale` k | `<expression> * k` |

### Highwind

Highwind scans each data source once per analysis. It reduces each unit's rows once per bucket,
then builds each window from those bucket values. Each aggregation therefore splits into four
parts:

- `bucket_aggregate`: reduces a unit's rows in one bucket to a number.
- `combine`: how bucket values combine over a window.
- `no_rows`: the value for a unit with no rows in the window.
- `finalize`: applied once to the combined value. It carries the threshold and scale.

| aggregation | `bucket_aggregate` | `combine` | `no_rows` | `finalize(x)` |
| --- | --- | --- | --- | --- |
| `sum` | `SUM(c)` | `SUM` | `0` | `x` |
| `count` | `COUNT(c)` | `SUM` | `0` | `x` |
| `count_where` | `COUNTIF(p)` | `SUM` | `0` | `x` |
| `any` | `COUNTIF(p)` | `SUM` | `0` | `CAST(x > 0 AS INT64)` |
| `recency_within` N | `MIN(mozfun.bits28.days_since_seen(c))` | `MIN` | `30` | `CAST(x < N AS INT64)` |
| with `threshold` | unchanged | unchanged | unchanged | `CAST(x <op> <value> AS INT64)` |
| with `scale` k | unchanged | unchanged | unchanged | `(finalize(x)) * k` |

The columns Highwind reads from each data source are derived from the V2 definitions: every
`column` and every condition column, grouped by `data_source`.

### Equivalence

The column and condition text is the same in both consumers. Only the wrapper differs. Over a
single bucket the four Highwind parts reduce to the Jetstream expression, so both consumers compute
the same value for a window. Highwind returns 0/1 integers where Jetstream returns booleans.

## Not supported yet

- Ratios, where one metric is divided by another.
- Histograms and percentiles.
- Averages, or any aggregation that cannot be split into per-bucket values that combine into the
  window value.
- `count_distinct`.
- OR, IN, NOT, LIKE, function calls and expressions in conditions or columns.
- Porting data sources. They stay in `definitions/`.
- Segments. They stay in `definitions/`.

## Example

A complete file for `definitions_v2/firefox_desktop.toml`:

```toml
[metrics.active_hours]
friendly_name = "Active hours"
description = "Time during which Firefox received user input."
data_source = "clients_daily"
aggregation = "sum"
column = "active_hours_sum"
cumulative_window = 7
repeat_windows = true

[metrics.active_hours.statistics.bootstrap_mean]

[metrics.retained]
friendly_name = "Retained"
data_source = "clients_daily"
aggregation = "sum"
column = "pings_aggregated_by_this_row"
threshold = { op = ">", value = 0 }
incremental_window = 7
repeat_windows = true
```

[example_config.toml.example](example_config.toml.example) shows every field.
