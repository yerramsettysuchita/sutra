#!/usr/bin/env sh
# IERB-P, corpus generation.
#
#   ./generate.sh              5,000 cases, 86 name forms, the default task
#   ./generate.sh 5000 3000    5,000 cases with a 3,000 form name vocabulary
#
# Writes benchmark/corpus/ and benchmark/gold/. Seed is fixed at 4471 and the
# generator is pure standard library, so output is byte identical anywhere.

set -e

CASES=${1:-5000}
POOL=${2:-86}
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
PYTHON=${PYTHON:-python3}

echo "IERB-P, generating $CASES cases with a $POOL form name vocabulary"

cd "$ROOT"
$PYTHON -m data.generator.generate \
  --cases "$CASES" \
  --name-pool "$POOL" \
  --out "$HERE/corpus"

$PYTHON "$HERE/make_gold.py" --corpus "$HERE/corpus" --out "$HERE/gold"

echo
echo "corpus  $HERE/corpus"
echo "gold    $HERE/gold"
echo
echo "Next:"
echo "  $PYTHON $HERE/baseline.py --corpus $HERE/corpus --out $HERE/baseline_output.csv"
echo "  $PYTHON $HERE/score.py $HERE/baseline_output.csv"
