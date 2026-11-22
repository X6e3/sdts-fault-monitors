#!/bin/sh
# Build the arXiv upload: main.tex, the figure sources and data, and the .bbl (arXiv does not need refs.bib).
#   sh make_arxiv.sh OUT_DIR      writes OUT_DIR/sdts-arxiv.tar.gz and OUT_DIR/main.pdf (the same build, for checking)
set -eu
here=$(cd "$(dirname "$0")" && pwd)
out=$1
work=$(mktemp -d)
cp "$here"/main.tex "$here"/refs.bib "$here"/fig_*.tex "$work"/
mkdir "$work"/figdata && cp "$here"/figdata/*.dat "$work"/figdata/
(cd "$work" && tectonic -X compile --keep-intermediates main.tex > build.log 2>&1)
mkdir -p "$out"
cp "$work"/main.pdf "$out"/main.pdf
(cd "$work" && tar czf "$out"/sdts-arxiv.tar.gz main.tex main.bbl fig_*.tex figdata/*.dat)
tar tzf "$out"/sdts-arxiv.tar.gz
rm -rf "$work"
