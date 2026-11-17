"""Environment lock for thermal protocol v2 runs (addendum A1.8).

    uv venv --python 3.12.13 .venv && uv pip install --python .venv/bin/python -r env/requirements-thermal-v2.txt

`check()` raises unless the running interpreter matches the lock; `describe()` returns what a result
package records (versions, HiGHS, platform, and a fingerprint of each installed wheel's RECORD file).
"""
import hashlib
import platform
import sys
from importlib import metadata

LOCK = {"python": "3.12.13", "numpy": "2.5.5", "scipy": "1.18.1", "highs": "1.12.0"}


def _highs():
    from scipy.optimize._highspy import _core as h
    return f"{h.HIGHS_VERSION_MAJOR}.{h.HIGHS_VERSION_MINOR}.{h.HIGHS_VERSION_PATCH}"


def describe():
    out = {"python": platform.python_version(), "implementation": platform.python_implementation(),
           "numpy": metadata.version("numpy"), "scipy": metadata.version("scipy"), "highs": _highs(),
           "platform": platform.platform(), "machine": platform.machine(), "executable": sys.executable}
    for dist in ("numpy", "scipy"):
        record = metadata.distribution(dist).read_text("RECORD") or ""
        out[f"{dist}_record_sha256"] = hashlib.sha256(record.encode()).hexdigest()
    return out


def check():
    got = describe()
    bad = {k: (v, got[k]) for k, v in LOCK.items() if got[k] != v}
    if got["implementation"] != "CPython":
        bad["implementation"] = ("CPython", got["implementation"])
    if bad:
        raise RuntimeError(f"environment differs from the thermal v2 lock: {bad}")
    return got


if __name__ == "__main__":
    import json
    print(json.dumps(check(), indent=2))
