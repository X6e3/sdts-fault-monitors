# PLAN-step3, addendum 2 (2026-11-23, during the idle phase of step3, before any load)

No change to the procedure, the criterion or the evaluation of PLAN-step3.md. At Can Koç's request ("macbookun altında
ntc transistör var onu da dahil et") one more record is kept, descriptive only:

- The Arduino transistor thermometers on the Arch machine (`serialtherm.sh`, sha256 41b67756…, the script of
  2026-11-22), raw readings a0 and a1, once a second, to `~/Research/sdts-runs/therm-20261123/transistors-step3.csv`
  on Arch. Started 2026-11-23 12:03:39 +0300, 109 s after step3's `idle0_start` (still in the idle phase), for 4500 s.
- Channels: on 2026-11-22 a0 was noted as the sensor at the MacBook's side and a1 as the room sensor; Can says a sensor
  is under the MacBook now. Which channel is where is to be confirmed by Can. The channels are not calibrated (no ice
  bath), so only changes over time are meaningful, not absolute temperatures.
- Clock: Arch minus Mac about +0.12 s (measured 12:05, round trip 0.26 s).
- This record is not used by `eval_step3.py` and does not enter the verdict. It may be reported alongside the result
  (for example, how far the ambient departs from a constant during the run).
