# Role: indexer
# Stage: index-hooks

Classify these Instagram reel hook templates. They come from the account owner's own list (library/hooks.txt);
`__` marks the blank the topic goes into. For each hook give exactly three things:

- family: one of these six, the closest fit:
  - tools-listicle: a list of tools, apps, resources or things ("3 tools for beginners I use daily for __")
  - how-to-system: a method, system, workflow, routine, setup, checklist, step by step ("My exact workflow for __")
  - mistake-warning: a mistake, a trap, a warning, "stop doing", "you are doing it wrong", "why it isn't working"
  - myth-contrarian: a myth, the truth nobody tells, a contrarian take, "everyone says X, but"
  - story-confession: a personal story, a confession, a failure, a feeling, what I learned, a revelation
  - transformation: a before and after, a change, "this changed everything", results over time, progress
- fits_problem_solution: true when the hook naturally opens a reel that presents the viewer's problem and then a
  solution (a tool, a method, a fix, a warning with a way out); false when it is a pure story, confession or mood
  line that does not promise a solution.
- issue: "" when the line is fine. Otherwise one short note (under 15 words) on a real problem: a grammar error, a
  typo, or a lost blank (a word is clearly missing where `__` should be, for example "changed everything in .").
  Do not comment on style, length or taste, and do not rewrite the hook.

## The hooks

{{HOOKS}}

## Your answer

Only this JSON object: {"hooks": [{"id": "<id as given>", "family": "<one of the six>", "fits_problem_solution":
true | false, "issue": ""}]}, one entry per id, every id exactly once, in the order given.
