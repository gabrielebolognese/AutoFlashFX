# Role: research
# Stage: 05-hooks

The hook judge's first filter (a local scoring script, no model) rejected most of the hooks you wrote: fewer than
{{MIN_SURVIVORS}} passed. Write {{N_NEW}} new hooks that fix exactly what the filter flagged, so the judge has
enough to choose from. The rules of the first round still apply (facts from the research only, {{MAX_WORDS}}
spoken words or fewer, 6 on-screen words or fewer, a concrete marker, no em dash). Answer with only the JSON
object described at the end.

## Hooks that passed (keep them; do not repeat them)

{{SURVIVORS}}

## Hooks that failed, with the filter's reasons

{{FAILURES}}

## What the filter measures

- length: it likes 5 to 12 spoken words; my own cap is {{MAX_WORDS}} words (under {{MAX_SECONDS}} seconds at
  {{WPM}} words per minute), so write 5 to {{MAX_WORDS}} words
- specificity: a number, a name or a tool in the line
- stakes: a word that puts something on the line (stop, never, wrong, mistake, cost, lost, without, before,
  instead, only, nobody, still, actually)
- front-loading: the concrete word within the first four words; no weak opener (so, hey, today, this is, have you,
  in this, one of, a lot)
- address: speak to the viewer (you, your) or open with an imperative
- dealbreakers: "stop scrolling", a greeting, "in this video", a hashtag, an emoji

## The templates (one hook per template_id; a template whose earlier hook failed may be used again)

{{TEMPLATES}}

{{NOTE}}
## Your answer

Only this JSON object: {"hooks": [{"template_id": "<as listed>", "family": "<the template's family>", "spoken":
"...", "on_screen": "...", "marker": "...", "marker_kind": "tool" | "number" | "time"}], "notes": ""}
