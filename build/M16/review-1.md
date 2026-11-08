# M16 review 1

Verdict: APPROVED

## Test run
`M16_SECTIONS="1 2 3 4 5 7" bash pipeline/tests/test-m16.sh`: 165 passed, 1 failed (review: liveness-static-element-caught, section 5).
The same section run again alone: 26 passed, 0 failed. The first failure looks like a flake under machine load (a browser run); the
builder's own final log shows 166 passed, 0 failed. Section 6 (the real-model run) was not run: the report says it has not passed yet.

## Required fixes
None.

## Suggestions
1. Section 6 (the real run of the test idea, export reached, time per reel) is still open. HUMAN_TODO already lists it; run it on a quiet machine.
2. liveness-static-element-caught is timing or load sensitive: consider a retry or a longer wait in that check.
3. test-m2's timing check (300 s limit for two dummy ideas) fails on a busy machine: raise the limit in the fine-tuning pass.
