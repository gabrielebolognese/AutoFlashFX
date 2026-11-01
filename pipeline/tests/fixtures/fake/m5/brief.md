## 1. The one idea

Anthropic ships an official Claude Code plugin called frontend-design that stops Claude from building the generic, AI-looking website everyone recognises. The one specific true thing the reel stands on is the install line (facts.md#2): `/plugin install frontend-design@claude-plugins-official` inside a Claude Code session, or `claude plugin install frontend-design@claude-plugins-official` from the shell. After that the skill switches on by itself for any frontend request (facts.md#4). The reel shows what the skill actually does: it makes Claude plan a palette, the type and the layout, review the plan against a list of AI tells, and only then write code (facts.md#9). The reel must not claim that the skill guarantees a site never looks AI-made (facts.md#12 says the brief's own words win), it must not quote the November 2025 advice about Inter and purple gradients as the current text (pitfalls), and it must not invent a before-and-after benchmark, because none exists for the current version.

## 2. The viewer

The share identity is "if you ship landing pages or client sites built with Claude Code". The viewer is a solo developer, a freelancer or a small studio that delivers websites fast with AI help and gets paid by clients who look at the result, not at the prompt. Their problem in their own words: "Every site I build with AI ends up with the same rounded cards, soft grey shadows and all-caps labels, and clients can tell right away." The moment they feel it is the client call where someone says "it looks a bit like a template" or "did you make this with AI", and the developer has no answer except another round of manual CSS fixes. A second moment is scrolling their own portfolio and seeing that three different clients got the same page with different logos.

## 3. The promise and the payoff

The hook promises a way to stop the AI look at the source, with one named tool and one concrete step. The payoff beat is the install line shown on screen together with the two-pass behaviour: Claude writes a design plan with four to six named hex colors, typefaces and a layout with ASCII wireframes, reviews it against the brief and the list of tells, and only then codes (facts.md#9). The payoff must land before the halfway mark and must show something checkable: the command, the version number 1.1.1 (numbers.json) and the Anthropic verified badge with 1,134,112 installs on the marketplace page (facts.md#14, asset 02-plugin-page.png). The last beat repeats the hook's key word before the single ask.

## 4. Facts to use

- facts.md#2: the install command, exactly `/plugin install frontend-design@claude-plugins-official` (session) and `claude plugin install frontend-design@claude-plugins-official` (shell). Good for a step beat and for the on-screen command card.
- facts.md#4: "Claude automatically uses this skill for frontend work." Good for a mechanism beat: nothing to invoke, you just ask for a UI.
- facts.md#1: the plugin lives in anthropics/claude-plugins-official under plugins/frontend-design, with plugin.json, SKILL.md, a LICENSE and a README. Good for a proof beat with the repo screenshot (01-repo.png).
- facts.md#5: the skill lists five looks AI design clusters around, including a warm cream background near #F4F1EA with a terracotta accent near #D97757, which it calls Anthropic's own Claude-interaction accent. Good for a surprise beat: Anthropic flags its own color.
- facts.md#6: the SaaS card kit as a tell: identical rounded cards, one border-radius on everything, the same soft grey shadow rgba(0,0,0,.1), gradient washes as decoration. Good for a comparison or a before-after beat; keep the exact shadow value.
- facts.md#7: the commonest tells of a generated page: accenting one word in a headline, all-caps labels, unnecessary labels above content, 01 / 02 / 03 markers on content that is not a sequence, an arrow added to button text. Good for a number beat (a short list the viewer can check on their own site).
- facts.md#8: fade-and-slide-up entrances on every section and hover transitions on every card read as AI-generated; the skill asks for one orchestrated moment instead. Good for a mechanism beat about motion.
- facts.md#9: two passes: a design plan (4 to 6 named hex colors, typefaces, layout with ASCII wireframes, principles), then a review that revises anything generic, then code. Also a quality floor: responsive down to mobile, visible keyboard focus, reduced motion respected. The core mechanism beat.
- facts.md#11: Apache 2.0 licensed. Good for a trust aside if there is room.
- facts.md#13: Anthropic's own article says that without guidance an LLM landing page "will almost always conform to Inter fonts, purple gradients on white backgrounds, and minimal animations", blaming "distributional convergence". Good for the stake beat, quoted as Anthropic's own words about the problem, not as the current skill text.
- facts.md#14: the Claude marketplace page lists frontend-design as "Anthropic verified" with 1,134,112 installs on 2026-11-01. Good for a proof beat; say "over a million installs" in speech and show the exact number on the card.
- numbers.json: plugin version 1.1.1; the SKILL.md last edited 2026-09-01; palette size 4 to 6 named hex values; line length under 80 characters. Good for small number cards.
- facts.md#10: the same skill also ships in anthropics/skills inside example-skills, which installs 12 skills at once. Good for a pitfall aside: use the single-plugin route.
- facts.md#3: Claude Code adds the official marketplace for you at the first interactive session, so no marketplace add step is needed. Good to keep the install beat honest and short.

## 5. Facts to avoid and pitfalls

- The skill has been rewritten since launch: the November 2025 advice (avoid Inter, avoid purple gradients, use bold animation) is not the current text. Quote the current SKILL.md tells (cream plus terracotta, SaaS card kits, all-caps eyebrows, arrows on buttons, fade-up on every section).
- The marketplace page and the README still say "high-impact animations" and "scroll-triggered interactions", while the current SKILL.md says to use motion sparingly. Do not present scroll animations as what the skill pushes for.
- The plugin is no longer in the anthropics/claude-code repo; older tutorials that link there are out of date. Point to claude-plugins-official.
- `/plugin` works only in an interactive Claude Code session; in `claude -p` it answers that it is not available. The shell form is `claude plugin install ...`.
- The brief always wins: if the user asks for a cream and serif look, the skill builds it. Never say "guarantees", "never looks AI again" or "fixes every site".
- Unverified: the exact install output for this plugin, the token cost shown in the details pane, any measured before-and-after benchmark for the current version. None of these go in the script.
- Numbers: the install count changes daily; say "over a million" aloud and date the exact figure on screen.

## 6. Suggested beat sheet

1. Hook (0 to 2 s, type pain-payoff): the judge's winning line, spoken and on screen, exactly as judged.
2. Stake (2 to 7 s, type pain-payoff, facts.md#13): "If you ship client sites with Claude Code, you know the look: same cards, same shadows, same all-caps labels. Anthropic's own words: AI pages almost always converge on Inter and purple gradients."
3. Tool (type tool, facts.md#1 and #14): "Anthropic ships a fix as an official plugin: frontend-design. Anthropic verified, over a million installs." Card: the marketplace page.
4. Step (type step, facts.md#2 and #3): "One command: /plugin install frontend-design@claude-plugins-official. No marketplace setup, it is already there." Card: the command.
5. Mechanism (type mechanism, facts.md#4 and #9): "Then you just ask for a UI. Before any code, Claude writes a plan: four to six named colors, the typefaces, the layout as wireframes." Card: PLAN, REVIEW, CODE.
6. Number (type number, facts.md#7 and #6): "It checks the plan against a list of tells: all-caps labels, arrows on buttons, the rgba(0,0,0,.1) shadow on every card, 01 02 03 markers on things that are not a sequence." Card: the tells as a checklist.
7. Proof (type proof, facts.md#5): "It even flags Anthropic's own terracotta, #D97757 on cream, as an AI tell." Card: the color chips.
8. Comparison (type before-after, facts.md#8): "Motion too: no fade-up on every section. One orchestrated moment instead."
9. Payoff (type pain-payoff, facts.md#12): "It is guidance, not magic: if you ask for the cream look, you get the cream look. But the defaults stop being the defaults."
10. Ask (type pain-payoff): the keyword line that repeats a hook word, see section 7.

Target length: 25 to 40 seconds at the creator's measured pace. Beats 6 and 7 can merge if the cut needs it; beat 8 is the first to drop.

## 7. The ask

Comment keyword: TELLS. Deliverable (NEW, to create): a one-page PDF checklist of the AI design tells named in the current SKILL.md, plus the exact install command for a Claude Code session and for the shell. Two candidate closing lines, each repeating a word from the hooks so the replay loops:

- "Comment TELLS and I send you the full list of AI tells, with the install command. Then stop shipping the default look."
- "Want the checklist Anthropic itself uses? Comment TELLS. One word, one plugin, no more AI-looking pages."

No second ask: no follow, no save, no link in the spoken script.

## 8. On-screen material

- 01-repo.png: the GitHub folder anthropics/claude-plugins-official/plugins/frontend-design with its README (what it does, example prompts). Use for the tool beat.
- 02-plugin-page.png: the Claude marketplace page with the Anthropic verified badge, 1,134,112 installs and the Install in Claude Code button (a cookie banner sits bottom right, crop it). Use for the proof beat.
- 03-skill-md.png: SKILL.md on GitHub, the frontmatter description and the opening design principles with the list of typographic tells. Use for the number beat.
- 04-blog.png: Anthropic's article 'Improving frontend design through Skills', November 12, 2025 (cookie banner bottom right). Use for the stake beat, labelled as the 2025 article.
- 05-install-docs.png: the Claude Code docs page 'Install and manage plugins' with the /plugin install flow. Use for the step beat.
- Numbers that deserve a card: 1,134,112 installs (dated 2026-11-01), version 1.1.1, 4 to 6 named hex colors, the two hex values #F4F1EA and #D97757, the shadow rgba(0,0,0,.1).

## 9. Words and tone

Use: tell, default look, template look, plan then code, one command, official plugin, Anthropic verified. Avoid: revolutionary, game changer, insane, unlock, seamless, elevate, guarantee, never again, 10x. Names: Claude Code (two words, capital C twice), frontend-design (lower case, hyphen, say "frontend design"), claude-plugins-official (say "the official Claude plugins marketplace"), SKILL.md (say "the skill file"), rgba(0,0,0,.1) (say "the same soft grey shadow", show the value on screen), #D97757 (say "Anthropic's terracotta", show the hex). Tones that fit this angle: insider (the creator has read the actual SKILL.md and quotes the tells), calm expert (plain steps, no hype, the install line as the centre), warning (the client can tell, and here is the fix). Contrarian works only on the terracotta beat; confession does not fit, because the facts are Anthropic's, not the creator's story.
