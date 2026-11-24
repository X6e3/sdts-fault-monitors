# OBD record of 30 July 2026 (CC BY 4.0)

Two OBD-II recordings of a Ford Fiesta 1.4 (petrol) on 30 July 2026, the day its cylinder-head gasket failed, made with
Car Scanner (`19-39-36` and `21-00-03`, the start times). Released for a later study, in which a monitor is applied to
the record under a plan fixed before the run; the current paper does not use it.

| column | meaning |
|---|---|
| `record` | the recording it comes from (its start time) |
| `clock_s` | local clock time, seconds after midnight |
| `signal` | `ect_C` (engine coolant temperature, °C, in steps of 1 °C), `rpm` (engine speed, rev/min), `speed_kmh` (vehicle speed, km/h) |
| `value` | the reading |

Long format, one reading per row, nothing smoothed or resampled. Made by `experiments/obd/extract_fiesta.py` from the
Car Scanner exports, which also hold signals that are not released.
