#!/bin/sh
# Builds the files Control Engineering Practice asks for at submission into OUT (default ./submission):
#   fig1.pdf ... fig5.pdf  each figure as a separate vector PDF, at the size, fonts (STIX, Latin Modern Sans, \small)
#                          and width (column 238.25444pt, text 494.50888pt) it has in main.pdf;
#   highlights.txt         the highlights of main.tex, one per line;
#   source/                main.tex, body.tex and sec_j713.tex with each \input{fig_*} replaced by
#                          \includegraphics{figN.pdf}, the class, style and bibliography files and the figures,
#                          built once to check that it gives the same pages as main.pdf;
#   supplement.pdf         the supplementary material (built from supplement.tex against the source/ build).
# Usage, from paper/journal after main.pdf is built:  sh make_submission.sh [OUT]
set -eu
OUT=${1:-submission}
HERE=$(pwd)
test -f main.tex && test -f main.pdf || { echo "run from paper/journal after building main.pdf" >&2; exit 1; }
mkdir -p "$OUT/source"
OUT=$(cd "$OUT" && pwd)
W=$(mktemp -d)
trap 'rm -rf -- "${W:?}"' EXIT
cp -R fig_*.tex figdata "$W/"
COLUMN=238.25444pt
TEXT=494.50888pt
n=0
for spec in fig_j713:$COLUMN fig_window:$TEXT fig_memory:$COLUMN fig_trace:$COLUMN fig_cells:$TEXT; do
  n=$((n + 1))
  f=${spec%%:*}; w=${spec#*:}
  {
    printf '%s\n' '\documentclass[border=0pt]{standalone}'
    printf '%s\n' '\usepackage[T1]{fontenc}'
    printf '%s\n' '\usepackage{amsmath,amssymb}'
    printf '%s\n' '\usepackage{stix}'
    printf '%s\n' '\usepackage[scaled=.85]{inconsolata}'
    printf '%s\n' '\usepackage[svgnames,dvipsnames]{xcolor}'
    # the figure preamble of main.tex: pgfplots, colours, styles, macros
    sed -n '/^\\usepackage{pgfplots}/,/^\\setlist/p' "$HERE/main.tex" | grep -v '^\\setlist' | grep -v 'newtheorem'
    printf '%s\n' '\begin{document}'
    printf '%s\n' "\\setlength{\\linewidth}{$w}\\sffamily\\small%"
    printf '%s\n' "\\input{$f.tex}%"
    printf '%s\n' '\end{document}'
  } > "$W/fig$n.tex"
  (cd "$W" && tectonic -X compile "fig$n.tex" > "fig$n.log" 2>&1) || { cat "$W/fig$n.log" >&2; exit 1; }
  cp "$W/fig$n.pdf" "$OUT/fig$n.pdf"
  cp "$OUT/fig$n.pdf" "$OUT/source/fig$n.pdf"
done
# highlights, one per line
sed -n '/\\begin{highlights}/,/\\end{highlights}/p' main.tex | sed -n 's/^\\item //p' | sed 's/\\%/%/g' > "$OUT/highlights.txt"
# the source with graphics files
cp cas-dc.cls cas-common.sty cas-model2-names.bst refs.bib main.bbl "$OUT/source/"
cp -R thumbnails "$OUT/source/"
python3 - "$OUT/source" <<'EOF'
# The submitted source must build on its own: references to the supplement (xr) become their printed numbers.
import re, sys
from pathlib import Path
out = Path(sys.argv[1])
def labels(aux):
    return {m.group(1): m.group(2) for m in re.finditer(r"\\newlabel\{([^}]*)\}\{\{([^}]*)\}", Path(aux).read_text())}
sup, own = labels("supplement.aux"), labels("main.aux")
sup_only = {k: v for k, v in sup.items() if k not in own and not k.startswith("tocindent")}
names = ["fig_j713", "fig_window", "fig_memory", "fig_trace", "fig_cells"]
fixed = 0
for f in ("main.tex", "body.tex", "sec_j713.tex"):
    s = Path(f).read_text()
    for i, n in enumerate(names, 1):
        s = re.sub(r"\\input\{" + n + r"(\.tex)?\}", r"\\includegraphics{fig%d.pdf}" % i, s)
    def rep(m):
        global fixed
        if m.group(1) in sup_only:
            fixed += 1
            return sup_only[m.group(1)]
        return m.group(0)
    s = re.sub(r"\\ref\{([^}]*)\}", rep, s)
    if f == "main.tex":
        s = s.replace("\\usepackage{xr}\n\\externaldocument[]{supplement}\n", "")
    (out / f).write_text(s)
left = [l for l in re.findall(r"\\ref\{([^}]*)\}", "".join((out / f).read_text() for f in ("main.tex", "body.tex", "sec_j713.tex"))) if l not in own]
print(f"supplement references fixed: {fixed}; references to unknown labels left: {left}")
assert not left and "externaldocument" not in (out / "main.tex").read_text()
EOF
(cd "$OUT/source" && tectonic -X compile --keep-intermediates main.tex > build.log 2>&1 && rm -f main.aux main.out main.blg main.abs)
cp supplement.pdf "$OUT/supplement.pdf"
echo "built: $(ls "$OUT")"
