"""I1 (third addendum): every field equal except seconds, step_ms, fold_step_ms. usage: i1_compare.py OLD_DIR NEW_DIR"""
import json, sys
from pathlib import Path
WALL = {"seconds", "step_ms", "fold_step_ms"}
old, new = Path(sys.argv[1]), Path(sys.argv[2])
ko = {p.relative_to(old) for p in old.rglob("*.json") if p.name not in ("selection.json", "memory.json")}
kn = {p.relative_to(new) for p in new.rglob("*.json") if p.name not in ("selection.json", "memory.json")}
diff, same = [], 0
for k in sorted(ko | kn):
    if k not in ko or k not in kn:
        diff.append((str(k), "missing on one side")); continue
    a, b = (json.loads((d / k).read_text()) for d in (old, new))
    fa = {x: v for x, v in a.items() if x not in WALL}; fb = {x: v for x, v in b.items() if x not in WALL}
    if fa == fb: same += 1
    else: diff.append((str(k), sorted(x for x in set(fa) | set(fb) if fa.get(x) != fb.get(x))))
print(json.dumps({"records": len(ko | kn), "identical_except_wall_clock": same, "differ": diff}, indent=1))
