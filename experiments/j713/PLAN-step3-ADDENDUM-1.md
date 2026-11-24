# PLAN-step3, addendum 1 (2026-11-23, before any step3 data exist)

No change to the procedure, the criterion or the code of PLAN-step3.md (manifest sha256 d84cacf4…). This records
Can Koç's conditions, given before the run, and his data-release decision.

1. The study measures how well the two-node model represents J713's real temperature behaviour. The paper's 0.3 °C
   measurement-noise bound is not used as the criterion for the model's prediction error; the criterion is that of
   section 4 (Ts0P rms ≤ 0.25 °C and largest absolute error ≤ 0.60 °C).
2. Development results stay separate. The criterion is frozen before the new run and is not changed whatever the
   result; a FAIL is recorded as FAIL.
3. The smallest error bound under which the model would hold on this device (the largest absolute error of Ts0P on
   step3) is reported separately and compared with the paper's 0.3 °C, but not treated as equivalent to it.
   (Interpretation note: that bound contains the model's error, the sensor's quantization and noise, and the
   ambient's departure from a constant; the paper's δ bounds measurement noise only.)

Data release (approved by Can, 2026-11-23): the columns time, PSTR, Ts0P, Ts1P and TB0T of step1, step2 and step3,
with their phases files, under CC BY 4.0, in the SDTS repository with the plan and the scripts. The other sensor
columns stay private.
