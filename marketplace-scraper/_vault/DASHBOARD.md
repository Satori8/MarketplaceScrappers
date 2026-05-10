# Dashboard

## Active Projects

```dataview
LIST
FROM "Projects"
WHERE file.name = "INDEX"
SORT file.mtime DESC
```

## Open Tasks

```dataview
TASK
FROM ""
WHERE !completed
SORT file.mtime DESC
```

## Recently Edited Notes

```dataview
TABLE file.mtime AS "Updated"
FROM ""
WHERE !contains(file.path, ".obsidian")
SORT file.mtime DESC
LIMIT 20
```

## Inbox

```dataview
LIST
FROM "00 Inbox"
SORT file.mtime DESC
```

