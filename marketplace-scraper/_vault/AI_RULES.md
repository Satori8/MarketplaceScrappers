# AI Rules

These rules apply when using Copilot, Codex, ChatGPT, or local AI tools with this vault.

## Operating Mode

Use this pattern:

```text
read many -> propose plan -> edit few
```

AI may read broad context, but should only edit specific agreed files.

## Language

Write new vault notes in Russian by default.

Exceptions:

- keep original language when editing an existing note that is clearly in another language;
- use Ukrainian for final Ukrainian-language content assets;
- use English inside prompts, code, API docs, and source quotes when needed.

## Do

- Update `INDEX.md`, `TASKS.md`, `DECISIONS.md`, and concise summaries.
- Create `*_draft.md` before replacing important notes.
- Preserve original prompts and source notes unless explicitly asked to rewrite.
- Use links between project notes and external folders.
- Mark uncertainty instead of inventing facts.

## Do Not

- Do not dump long raw AI answers into permanent notes.
- Do not rewrite the whole vault in one pass.
- Do not move Obsidian project folders without a dry-run.
- Do not expose secrets, API keys, accounts, phone numbers, or emails in summaries.
- Do not edit `.obsidian` unless the task is plugin configuration.

## Sensitive Zones

- `90 Private/`
- scraper configs with API keys
- browser profiles
- account lists
- files containing phones/emails

## Good AI Tasks

- "Update this project INDEX from the files in this folder."
- "Find contradictions between these prompt files."
- "Turn this messy note into decisions, tasks, and open questions."
- "Create a dry-run cleanup plan."
- "Summarize related notes into a stable brief."
