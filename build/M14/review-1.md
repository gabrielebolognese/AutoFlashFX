# M14 review 1

Verdict: APPROVED

Acceptance test: `bash pipeline/tests/test-m14.sh` run once: 77 passed, 0 failed (it matches build/M14/test-m14.log). The earlier milestones' reruns recorded in build/M14/earlier-tests/ all passed, so I did not repeat them.

## Required fixes
None.

## Suggestions
- test-m14 takes about 15 to 25 minutes, so it needs a background run with a long timeout.
- The working tree has an uncommitted build-runner.sh change and a deleted build-runner.new.sh. These are build-runner files, not M14 code.
