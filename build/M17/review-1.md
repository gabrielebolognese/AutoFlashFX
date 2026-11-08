# M17 review 1

Verdict: APPROVED

The acceptance test (`bash pipeline/tests/test-m17.sh`) ran once: 80 passed, 0 failed. The diff touches only build/, pipeline/tests/ and docs. The manifest, refindex, config keys, risks and baseline that M18 needs are all in build/M17/.

## Required fixes
None.

## Suggestions
- The baseline for the other 18 test files predates test-m17. This is documented in the report.
- The real folder has no runs/ or exports/, so those moves are proven only on the fixture.
