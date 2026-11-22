#!/bin/sh
# Build the README's figure from the paper's own figure source (Figure 2, fig_memory.tex) and data.
#   sh make_readme_figure.sh      writes fig-memory.png (white background, 4x) and fig-memory.pdf next to this script
# Needs Tectonic and, for the PNG, macOS (pdf_to_png.swift uses CoreGraphics).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
pre="$here/../preprint"
work=$(mktemp -d)
cp "$here"/readme_fig_memory.tex "$pre"/fig_memory.tex "$work"/
mkdir "$work"/figdata && cp "$pre"/figdata/fig1_*.dat "$work"/figdata/
(cd "$work" && tectonic -X compile readme_fig_memory.tex > build.log 2>&1)
cp "$work"/readme_fig_memory.pdf "$here"/fig-memory.pdf
swift "$here"/pdf_to_png.swift "$here"/fig-memory.pdf "$here"/fig-memory.png 4
rm -rf "$work"
