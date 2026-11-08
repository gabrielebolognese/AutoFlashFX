#!/usr/bin/env bash
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
bash pipeline/tests/test-m2.sh > build/M16/earlier-tests/test-m2-b.log 2>&1
echo "test-m2: exit $?, $(grep -c '^PASS' build/M16/earlier-tests/test-m2-b.log) passed, $(grep -c '^FAIL' build/M16/earlier-tests/test-m2-b.log) failed" >> build/M16/earlier-tests/summary-b.txt
M16_SECTIONS="1 2 3 4 5 7" bash pipeline/tests/test-m16.sh > build/M16/final-tests/test-m16-final.log 2>&1
echo "test-m16: exit $?, $(grep -c '^PASS' build/M16/final-tests/test-m16-final.log) passed, $(grep -c '^FAIL' build/M16/final-tests/test-m16-final.log) failed" >> build/M16/earlier-tests/summary-b.txt
echo done >> build/M16/earlier-tests/summary-b.txt
