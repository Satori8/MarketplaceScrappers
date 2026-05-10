# Obsidian AI Workflow

## Stack

Installed plugins:

- Copilot - chat and note-aware AI inside Obsidian.
- Local REST API - lets external agents/tools access the vault while Obsidian is open.
- Dataview - dashboards from Markdown metadata and tasks.
- Templater - structured note templates.
- AI Templater - AI-assisted template flows.

## Best Use

Use plugins by job:

| Job | Tool |
|---|---|
| Ask questions about current note | Copilot |
| Find related notes | Copilot / semantic search if enabled |
| Generate recurring note skeletons | Templater |
| Track projects/tasks | Dataview |
| Let Codex reorganize/refactor notes | Filesystem or Local REST API |
| Heavy project audit | Codex |

## Daily Capture

1. Capture raw thoughts into `00 Inbox`.
2. At end of day, ask AI to sort them:

```text
Review 00 Inbox. Propose where each note belongs.
Output a dry-run table: note, destination, reason, action.
Do not move files.
```

3. Move only after reviewing the plan.

## Weekly Review

```text
Review Home, PROJECTS, TASKS, and active project INDEX files.
Update TASKS with only concrete next actions.
Mark stale or duplicated notes.
Do not rewrite source notes.
```

## Project Review

```text
Review this project folder.
Update INDEX.md with:
- objective
- current state
- external folders
- next actions
- risks
- stale notes
Preserve source notes.
```

## Prompt Review

```text
Compare all prompt files in this project.
Find contradictions, duplicates, and obsolete instructions.
Propose a canonical hierarchy:
1. global rules
2. style guide
3. task prompt
4. output schema
```

## Hard Rule

Copilot is for fast thinking. Codex is for structural work.

Do not let Copilot generate huge permanent notes unless the result is edited into a concise stable document.

