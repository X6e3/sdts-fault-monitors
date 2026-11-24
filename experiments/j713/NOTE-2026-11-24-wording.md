# Note on the wording of step 3's error figure (2026-11-24)

RECORD-2026-11-23-step3.md (stamped; not edited) calls 0.205 °C "the error bound the model needs on this device".
It is the largest absolute residual of the least-squares trajectory (TA and c0 fitted, rate parameters from step 1),
so it is an upper bound on the smallest uniform error bound for this run, not that bound itself; no minimax fit was
made. When the J713 run enters the paper: "the largest absolute residual of the fitted trajectory was 0.205 °C on
this run". Raised by a review of the step-3 folder on 2026-11-24.
