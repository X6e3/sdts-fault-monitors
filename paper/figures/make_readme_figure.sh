#!/bin/sh
# Build the README's figures from the paper's own figure sources and data (Figures 1, 2 and 3).
#   sh make_readme_figure.sh      writes fig-window, fig-memory and fig-trace (.png at 4x on white, and .pdf) here
# Needs Tectonic and, for the PNGs, macOS (pdf_to_png.swift uses CoreGraphics).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
pre="$here/../preprint"
for name in window memory trace; do
  work=$(mktemp -d)
  sed "s/FIGNAME/fig_$name/" "$here"/readme_figure.tex > "$work"/readme_fig.tex
  cp "$pre"/fig_$name.tex "$work"/
  mkdir "$work"/figdata && cp "$pre"/figdata/*.dat "$work"/figdata/
  (cd "$work" && tectonic -X compile readme_fig.tex > build.log 2>&1)
  cp "$work"/readme_fig.pdf "$here"/fig-$name.pdf
  swift "$here"/pdf_to_png.swift "$here"/fig-$name.pdf "$here"/fig-$name.png 4
  rm -rf "$work"
done
