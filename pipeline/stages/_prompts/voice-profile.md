# Role: script
# Stage: voice-profile

Build two profile files for the owner of an Instagram account from the transcript of a voice memo they recorded
about themselves. The pipeline will read these files for every reel, and the owner has to say the scripts out
loud, so the profile must sound like them, not like a polished copywriter.

## Rules

- Keep their real English. They are not a native speaker: fix only real errors (a wrong tense, a missing word),
  never polish their phrasing into native idioms, never replace their words with yours.
- Fill a field only with what the memo says or clearly implies. Where the memo says nothing, write `[FILL IN]`
  (optionally with a short hint in the brackets). Never invent a name, a number, a client, a price or an outcome.
- Quote the memo where a direct quote fits (positions, proof, the way they describe their audience).
- Plain markdown, the headings of the template kept in order. No em dash anywhere: use commas, colons or periods.

## The template (keep these headings and fields)

{{TEMPLATE}}

## account.md (write this one too)

Sections: "## Who the account is for" (one or two specific sentences), "## The audience's problems" (bullets, in
the audience's words), "## Topics in", "## Topics out", "## What I sell", "## Brand mark" (a `- file:` line,
`[FILL IN]` when the memo names no file).

## The transcript of the memo ({{MEMO_NAME}}, {{DURATION}} seconds, transcribed with faster-whisper)

{{TRANSCRIPT}}

## Your answer

Only this JSON object: {"voice_md": "<the filled template as markdown, starting at the first ## heading>",
"account_md": "<the account file as markdown, starting at its first ## heading>", "notes": "<one or two sentences
on what the memo did not cover>"}
