#!/usr/bin/env bash
#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
#
# Prints the native stack of every thread in each core dump in a folder,
# writes it next to the core as <core>.txt, then deletes the core.
#
# CI uses it after the tests: a test worker that crashes in native code
# (Qt, numpy, Basilisk) shows only "<no Python frame>" in Python's
# faulthandler output, and this gives the C/C++ frames instead.
#
#     scripts/print_core_backtraces.sh /tmp/cores
#
# The cores must be named core.<%E>.<%p> (kernel.core_pattern
# /tmp/cores/core.%E.%p): %E is the crashed program's path with "/"
# written as "!", which tells gdb which executable to load.
#
# Exits 0 when there are no cores, so it can run after every test step.
set -u

dir="${1:?usage: print_core_backtraces.sh <core folder>}"
shopt -s nullglob
cores=()
for path in "$dir"/core.*; do
    [[ "$path" == *.txt ]] || cores+=("$path")
done

if [[ ${#cores[@]} -eq 0 ]]; then
    echo "No core dumps in $dir."
    exit 0
fi

for core in "${cores[@]}"; do
    name="${core##*/}"
    name="${name#core.}"
    exe="${name%.*}"
    exe="${exe//!//}"
    if [[ ! -x "$exe" ]]; then
        echo "Executable '$exe' for $core not found; reading the core alone."
        exe=""
    fi
    echo "::group::Native stacks from $core (${exe:-unknown program})"
    # gdb selects the crashed thread on loading the core, so the first
    # backtrace is the crash; then every thread, then the loaded libraries.
    gdb -batch -nx -q \
        -ex "set debuginfod enabled off" \
        -ex "set pagination off" \
        -ex "echo \\n=== Crashed thread ===\\n" \
        -ex "bt 50" \
        -ex "echo \\n=== All threads ===\\n" \
        -ex "info threads" \
        -ex "thread apply all bt 50" \
        -ex "echo \\n=== Shared libraries ===\\n" \
        -ex "info sharedlibrary" \
        ${exe:+"$exe"} "$core" 2>&1 | tee "$core.txt"
    echo "::endgroup::"
    rm -f "$core"
done
