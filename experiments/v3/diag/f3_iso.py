"""ISOLATION-PLAN.md: F3 with every LP solved in a child process (variant F3-iso).

diag3_cw.rec_linprog calls the module-level `linprog`. Here that name is replaced by `isolated_linprog`, which sends
the LP to a long-lived child process and returns the child's answer as a plain result object with the fields F3 reads
(status, message, fun, x and the four multiplier arrays). If the child process ends while solving (any signal, an
abort) or does not answer within TIMEOUT seconds, the child is replaced and RuntimeError is raised in the caller.
RuntimeError is one of diag3_cw.SOLVER_ERRORS, so F3's solve_f3 counts the attempt as failed ("exception") and its
documented fallbacks apply, exactly as for any other failed attempt. Nothing else of F3 changes.

Simulated solver failure (the robustness test of ISOLATION-PLAN.md): `inject(rate_by_role, key)` makes the child end
itself (os._exit, or a signal) before solving on a hash-chosen subset of LPs, chosen per (row key, role, call count).
"""
import builtins
import hashlib
import multiprocessing as mp
import os
import signal
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import diag3_cw as C  # noqa: E402

TIMEOUT = 120.0
_ORIG = C.linprog


def _plain(res):
    m = lambda part: None if part is None else SimpleNamespace(marginals=np.asarray(part.marginals))
    return SimpleNamespace(status=int(res.status), message=str(res.message),
                           fun=None if res.fun is None else float(res.fun),
                           x=None if res.x is None else np.asarray(res.x),
                           lower=m(getattr(res, "lower", None)), upper=m(getattr(res, "upper", None)),
                           ineqlin=m(getattr(res, "ineqlin", None)), eqlin=m(getattr(res, "eqlin", None)))


def _child(conn):
    from scipy.optimize import linprog
    while True:
        try:
            msg = conn.recv()
        except EOFError:
            return
        c, kw, end = msg
        if end == "exit":
            os._exit(3)
        if end == "segv":
            os.kill(os.getpid(), signal.SIGSEGV)
        try:
            conn.send(("ok", _plain(linprog(c, **kw))))
        except Exception as e:                       # the solver raised: the caller re-raises the same class
            conn.send(("err", (type(e).__name__, str(e))))


class Solver:
    def __init__(self):
        # fork on Linux (a restart costs milliseconds); spawn elsewhere (macOS: fork after threads is unsafe)
        self.ctx = mp.get_context("fork" if sys.platform.startswith("linux") else "spawn")
        self.proc = self.conn = None
        self.n_restarts = 0
        self.start()

    def start(self):
        a, b = self.ctx.Pipe()
        self.proc = self.ctx.Process(target=_child, args=(b,), daemon=True)
        self.proc.start()
        b.close()
        self.conn = a

    def restart(self, why):
        try:
            self.proc.kill()
        except Exception:
            pass
        self.proc.join(5)
        self.n_restarts += 1
        self.start()
        return why

    def solve(self, c, kw, end=None):
        try:
            self.conn.send((c, kw, end))
            if not self.conn.poll(TIMEOUT):
                raise RuntimeError(self.restart(f"solver process: no answer in {TIMEOUT} s"))
            tag, val = self.conn.recv()
        except (EOFError, BrokenPipeError, ConnectionResetError, OSError):
            self.proc.join(5)
            code = self.proc.exitcode
            raise RuntimeError(self.restart(f"solver process ended (exit code {code})"))
        if tag == "err":                              # the solver raised in the child: the same class here
            name, text = val
            exc = getattr(builtins, name, None)
            raise (exc if isinstance(exc, type) and issubclass(exc, Exception) else RuntimeError)(text)
        return val


_SOLVER = None
_INJECT = {"rates": {}, "key": "", "count": {}, "log": {}, "current": None}
FIRST_ATTEMPT = C.ATTEMPTS[0]                     # (method, options) of the first of the three attempts


def inject(rates, key):
    """rates: {role kind: probability} for "fold", "range", "cert"; key: the row key (the hash's first part)"""
    _INJECT.update(rates=dict(rates), key=key, count={}, log={}, current=None)


def _role_kind():
    win = _INJECT.get("win")
    role = getattr(win, "role", None) if win is not None else None
    if role is None:
        return None, None
    kind = role[0] if isinstance(role, tuple) else str(role)
    return kind, role


def isolated_linprog(c, **kw):
    global _SOLVER
    if _SOLVER is None:
        _SOLVER = Solver()
    kind, role = _role_kind()
    rate = _INJECT["rates"].get(kind, 0.0)
    if (kw.get("method"), kw.get("options")) == FIRST_ATTEMPT:   # a new LP: decide once for all its attempts
        _INJECT["current"] = None
        if rate:
            n = _INJECT["count"].get(repr(role), 0)
            _INJECT["count"][repr(role)] = n + 1
            h = hashlib.sha256(f"{_INJECT['key']}|{role!r}|{n}".encode()).digest()
            if int.from_bytes(h[:8], "big") / 2 ** 64 < rate:
                _INJECT["current"] = "segv" if h[8] & 1 else "exit"
                _INJECT["log"][kind] = _INJECT["log"].get(kind, 0) + 1
    return _SOLVER.solve(c, kw, _INJECT["current"])


def install(win=None):
    """route F3's LPs through the child process; `win` (the window) lets the injection read the LP's role"""
    _INJECT["win"] = win
    C.linprog = isolated_linprog


def uninstall():
    C.linprog = _ORIG
    _INJECT["win"] = None
