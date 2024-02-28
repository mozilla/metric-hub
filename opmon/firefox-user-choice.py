pairs = [
    ('Success', 0),
    ('ErrProgID', 1),
    ('ErrHash', 2),
    ('ErrLaunchExe', 3),
    ('ErrExeTimeout', 4),
    ('ErrExeProgID', 5),
    ('ErrExeHash', 6),
    ('ErrExeRejected', 7),
    ('ErrExeOther', 8),
    ('ErrOther', 9),
    ('ErrBuild', 10),
]

for name, key in pairs:
    print(f"""[metrics.{name}_client_volume]
data_source = "firefox_userchoice"
select_expression = "CAST(MAX(key) = {key} AS INT64)"
type = "scalar"

[metrics.{name}_client_volume.statistics]
sum = {{}}
total_ratio = {{ denominator_metric = "total_client_volume" }}
""")

for name, key in pairs:
    print(f"""[metrics.{name}_event_volume]
data_source = "firefox_userchoice"
select_expression = "SUM(IF(key = {key}, value, 0))"
type = "scalar"

[metrics.{name}_event_volume.statistics]
sum = {{}}
total_ratio = {{ denominator_metric = "total_event_volume" }}
""")
