"""Fiesta 1.4, 2026-07-30 (the head-gasket day): the released columns and the figure data.

  python3 -I extract_fiesta.py RAW_DIR OUT_CSV FIG_DAT

RAW_DIR holds the two Car Scanner exports "2026-07-30 19-39-36.csv" and "2026-07-30 21-00-03.csv" (long format,
';'-separated: SECONDS;PID;VALUE;UNITS, SECONDS = local clock time in seconds after midnight). Only three signals are
released: engine coolant temperature (ECT, °C, 1 °C steps), engine speed (rpm) and vehicle speed (km/h). Nothing is
smoothed or resampled in OUT_CSV. FIG_DAT keeps, for the second record, every sample at which ECT changes value (plus
the last sample), which draws the same step curve.
"""
import csv
import sys
from pathlib import Path

KEEP = {"Engine coolant temperature": "ect_C", "Engine RPM": "rpm", "Vehicle speed": "speed_kmh"}
RECORDS = ("2026-07-30 19-39-36", "2026-07-30 21-00-03")


def read(path):
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in list(csv.reader(f, delimiter=";"))[1:]:
            if len(r) > 2 and r[1] in KEEP:
                try:
                    out.append((float(r[0]), KEEP[r[1]], float(r[2])))
                except ValueError:
                    pass
    return out


def main(raw, out_csv, fig_dat):
    raw = Path(raw)
    rows = {rec: read(raw / (rec + ".csv")) for rec in RECORDS}
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["record", "clock_s", "signal", "value"])
        for rec in RECORDS:
            for t, sig, v in rows[rec]:
                w.writerow([rec, "%.4f" % t, sig, "%g" % v])
    ect = [(t, v) for t, s, v in rows[RECORDS[1]] if s == "ect_C"]
    rpm = [(t, v) for t, s, v in rows[RECORDS[1]] if s == "rpm"]
    t0 = 21 * 3600
    keep, prev = [], None
    for t, v in ect:
        if v != prev:
            keep.append((t, v))
            prev = v
    keep.append(ect[-1])
    with open(fig_dat, "w") as f:
        f.write("% minutes after 21:00 (local), ECT in degC; every change of ECT in record 2026-07-30 21-00-03\n")
        f.write("min ect\n")
        for t, v in keep:
            f.write("%.4f %g\n" % ((t - t0) / 60, v))
    on = [t for t, v in rpm if v > 0]
    print("ECT samples", len(ect), "change points", len(keep), "first rpm>0 at %.4f min" % ((on[0] - t0) / 60))


if __name__ == "__main__":
    main(*sys.argv[1:4])
