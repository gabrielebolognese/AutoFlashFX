# Facts: Claude Code's frontend-design skill: it makes websites built with AI stop looking AI-generated. Show

Checked 2026-11-01. Every claim carries its source and the date it was checked; the claims are listed
in order of trust (primary: the official repo or docs; vendor: the maker's blog or announcement; press;
forum). A claim marked unverified could not be confirmed on that day; one marked false is contradicted
by its source. Numbers such as facts.md#3 point to the claims below.

## Core claim of the idea
Anthropic ships a frontend-design skill for Claude Code that steers Claude away from generic, AI-looking UI and can be installed as an official plugin.
Status: verified. The skill is live in anthropics/claude-plugins-official (plugins/frontend-design, plugin.json version 1.1.1, SKILL.md last edited 2026-09-01). Its description promises choices "that don't read as templated defaults". The Claude Code docs say plugins install with /plugin install <name>@claude-plugins-official.

## Claims
1. The frontend-design plugin lives in Anthropic's official plugin marketplace repo, under plugins/frontend-design. [primary, verified]: https://github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design (checked 2026-11-01)
   Note: The folder holds .claude-plugin/plugin.json, skills/frontend-design/SKILL.md, a LICENSE and a README.md.
2. Install command: /plugin install frontend-design@claude-plugins-official (in your shell: claude plugin install frontend-design@claude-plugins-official). [primary, verified]: https://code.claude.com/docs/en/discover-plugins (checked 2026-11-01)
   Note: The docs show this pattern using commit-commands and say to substitute the plugin name. The marketplace entry named frontend-design is confirmed in .claude-plugin/marketplace.json.
3. Claude Code adds Anthropic's official marketplace for you the first time you start an interactive terminal session, so no marketplace add step is needed. [primary, verified]: https://code.claude.com/docs/en/discover-plugins (checked 2026-11-01)
   Note: On a machine that has never run an interactive session, a script must first run claude plugin marketplace add anthropics/claude-plugins-official.
4. Once installed, the skill activates automatically for frontend work. You just ask Claude to build a UI. [primary, verified]: https://github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design (checked 2026-11-01)
   Note: README: "Claude automatically uses this skill for frontend work." Example prompts: "Build a landing page for an AI security startup".
5. The skill lists five looks that AI-generated design clusters around, including a warm cream background near #F4F1EA with a terracotta accent near #D97757, and a near-black background with one acid-green or vermilion accent. [primary, verified]: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md (checked 2026-11-01)
   Note: In the section 'Process: plan, review against the brief, build, critique'. It calls #D97757 "Anthropic's own Claude-interaction accent".
6. The skill names the SaaS-card kit as a tell: identical rounded cards, one border-radius on everything, the same soft grey shadow rgba(0,0,0,.1), and gradient washes as decoration. [primary, verified]: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md (checked 2026-11-01)
   Note: Trait 4 in the skill's calibration list.
7. The skill calls these the commonest tells of a generated page: accenting one word in a headline, all-caps labels, and unnecessary labels above content. It also flags '01 / 02 / 03' markers on content that is not a sequence, and a '→' added to button text. [primary, verified]: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md (checked 2026-11-01)
   Note: Quoted from the 'Design principles' section and trait 5 of the calibration list.
8. The skill says fade-and-slide-up entrances on every section and hover transitions on every card "read as AI-generated". It asks for one orchestrated moment instead. [primary, verified]: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md (checked 2026-11-01)
   Note: Design principles section, on motion.
9. The skill makes Claude work in two passes: first a design plan (4 to 6 named hex colors, typefaces, layout with ASCII wireframes, principles), then a review that revises anything generic, and only then code. [primary, verified]: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md (checked 2026-11-01)
   Note: The skill also sets a quality floor: responsive down to mobile, visible keyboard focus, reduced motion respected.
10. The same skill also ships in the anthropics/skills repo, inside the example-skills plugin: /plugin marketplace add anthropics/skills, then /plugin install example-skills@anthropic-agent-skills. [primary, verified]: https://github.com/anthropics/skills (checked 2026-11-01)
   Note: That route installs 12 example skills, not just this one. Its SKILL.md text matches the one in claude-plugins-official.
11. The skill is Apache 2.0 licensed. [primary, verified]: https://github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design (checked 2026-11-01)
   Note: The plugin's LICENSE was added on 2026-02-20 in the commit "Add Apache 2.0 LICENSE files to all internal plugins". The claude-plugins-official repo itself is Apache-2.0.
12. The skill does not guarantee a site never looks AI-made. It is a set of instructions, and the brief's own words override it. [primary, verified]: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md (checked 2026-11-01)
   Note: SKILL.md: "Where the brief pins down a visual direction, follow it exactly, the brief's own words always win, including when it asks for one of these looks."
13. Anthropic's article says that without guidance an LLM landing page "will almost always conform to Inter fonts, purple gradients on white backgrounds, and minimal animations", and it blames "distributional convergence". [vendor, verified]: https://claude.com/resources/articles/improving-frontend-design-through-skills (checked 2026-11-01)
   Note: Article 'Improving frontend design through Skills', dated November 12, 2025. The original /blog/ URL redirects here.
14. The Claude marketplace page lists frontend-design as "Anthropic verified" with 1,134,112 installs. [vendor, verified]: https://claude.com/marketplace/plugins/frontend-design (checked 2026-11-01)
   Note: Seen in the screenshot taken 2026-11-01. The count changes over time.

## Numbers
- frontend_design_plugin_version: 1.1.1 version (https://github.com/anthropics/claude-plugins-official/blob/main/plugins/frontend-design/.claude-plugin/plugin.json, checked 2026-11-01; Explicit version added on 2026-10-26.)
- installs_on_claude_marketplace: 1134112 installs (https://claude.com/marketplace/plugins/frontend-design, checked 2026-11-01; As shown on 2026-11-01.)
- anthropics_claude_plugins_official_stars: 45583 GitHub stars (https://github.com/anthropics/claude-plugins-official, checked 2026-11-01; From gh repo view on 2026-11-01.)
- anthropics_skills_stars: 185914 GitHub stars (https://github.com/anthropics/skills, checked 2026-11-01; From gh repo view on 2026-11-01.)
- skill_md_size: 71 lines (44 loc) · 9.17 KB file size (https://github.com/anthropics/claude-plugins-official/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md, checked 2026-11-01; As shown in the GitHub file header.)
- last_skill_md_content_update_plugin_repo: 2026-09-01 date (https://github.com/anthropics/claude-plugins-official/commit/44490cccaf6d9f82fdeec9416fbf7c9bd72575dc, checked 2026-11-01; Commit "Update /frontend-design SKILL.md".)
- last_skill_md_update_anthropics_skills: 2026-09-03 date (https://github.com/anthropics/skills/commit/41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f, checked 2026-11-01; Commit "Update frontend-design skill to avoid generic design defaults (#1713)".)
- anthropic_article_publish_date: November 12, 2025 date (https://claude.com/resources/articles/improving-frontend-design-through-skills, checked 2026-11-01; The article calls the original prompt a "~400 token prompt". The current SKILL.md is much longer (9.17 KB).)
- palette_size_the_skill_asks_for: 4-6 named hex values colors (https://github.com/anthropics/claude-plugins-official/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md, checked 2026-11-01; Part of the design-plan pass.)
- line_length_default: less than 80 characters characters (https://github.com/anthropics/claude-plugins-official/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md, checked 2026-11-01)

## Pitfalls
- The skill has been rewritten since launch. The November 2025 article's advice (avoid Inter, purple gradients, use bold animation) is not the current text. The current SKILL.md (2026-09) targets different tells: cream plus terracotta, dark plus acid-green, SaaS card kits, all-caps eyebrows, arrows on buttons. Quote the current SKILL.md.
- The marketplace page and the README still say "high-impact animations" and "scroll-triggered interactions", while the current SKILL.md says to use motion sparingly. Do not present scroll animations as what the skill pushes for.
- The plugin is no longer in the anthropics/claude-code repo. That repo's plugins folder now only holds a README pointing to anthropics/claude-plugins-official. Older tutorials that link there are out of date.
- /plugin only works in an interactive Claude Code session. In claude -p it replies "/plugin isn't available in this environment." Use claude plugin install from the shell instead.
- On a fresh machine where no interactive session has run, the official marketplace is not registered yet. Run claude plugin marketplace add anthropics/claude-plugins-official first.
- Cloud sessions (claude.ai/code) do not load plugins you installed locally.
- In a session, /plugin install opens a details panel and asks for a scope (user, project, local). It does not install instantly.
- The brief always wins. If you ask for a cream and serif look, the skill will build it. It is guidance, not a filter, and does not guarantee a site never looks AI-made.
- Installing via anthropics/skills (example-skills) brings 12 skills, not just frontend-design. For only this skill, use frontend-design@claude-plugins-official.
- Plugins can run hooks and MCP servers. The docs advise reading the details pane before installing. This one only contains a skill.

## One specific true thing (candidates)
- One command: /plugin install frontend-design@claude-plugins-official. After that it activates on its own for any frontend request.
- The skill calls out Anthropic's own brand color: a terracotta accent "near #D97757" on a cream background near #F4F1EA is listed as an AI tell.
- The skill names the SaaS-card kit as a tell: identical rounded cards, one border-radius everywhere, the same rgba(0,0,0,.1) shadow, gradient washes.
- Anthropic's own words: without guidance an LLM landing page "will almost always conform to Inter fonts, purple gradients on white backgrounds, and minimal animations".
- 1,134,112 installs and an "Anthropic verified" badge on the Claude marketplace page (as of 2026-11-01).

## Unverified or unsourced
- I did not run the install myself, so I did not see the exact output for frontend-design (scope prompt, 'Plugin is now active.'). The docs show this flow for commit-commands.
- I could not check the token context cost the /plugin details pane shows for frontend-design. It only appears inside Claude Code.
- I found no measured before and after benchmark from Anthropic for the current (2026-09) skill version. The article's examples describe the November 2025 prompt.
- I could not verify the secondhand LinkedIn quote ("We've released a new frontend design skill...") from search results against the original post.

## Assets (screenshots in 01-research/assets/)
- 01-repo.png: GitHub folder anthropics/claude-plugins-official/plugins/frontend-design with its README: what it does and example prompts. (https://github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design, captured 2026-11-01 03:23)
- 02-plugin-page.png: Claude marketplace page for frontend-design: Anthropic verified badge, 1,134,112 installs, Install in Claude Code button (cookie banner at bottom right). (https://claude.com/plugins/frontend-design, captured 2026-11-01 03:23)
- 03-skill-md.png: The SKILL.md on GitHub: the frontmatter description and the opening design principles, including the list of typographic tells. (https://github.com/anthropics/claude-plugins-official/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md, captured 2026-11-01 03:23)
- 04-blog.png: Anthropic article 'Improving frontend design through Skills', November 12, 2025, opening on Inter fonts and purple gradients (cookie banner at bottom right). (https://claude.com/blog/improving-frontend-design-through-skills, captured 2026-11-01 03:23)
- 05-install-docs.png: Claude Code docs page 'Install and manage plugins', with the /plugin install <name>@claude-plugins-official flow. (https://code.claude.com/docs/en/discover-plugins, captured 2026-11-01 03:23)

## Research summary
The reel can safely say three things. frontend-design is an official, Anthropic-verified Claude Code plugin (v1.1.1, 1,134,112 installs). It installs with /plugin install frontend-design@claude-plugins-official and then activates on its own for frontend work. Its current SKILL.md names specific AI tells to avoid (cream plus #D97757 terracotta, SaaS card kits with rgba(0,0,0,.1) shadows, all-caps eyebrows, arrows on buttons, fade-up on every section) and makes Claude plan, review and only then code. Avoid presenting the old November 2025 guidance (Inter, purple gradients, bold scroll animations) as what the skill says now. Don't point to the anthropics/claude-code repo as its home, and don't promise it guarantees a non-AI look, since the user's brief overrides it.
