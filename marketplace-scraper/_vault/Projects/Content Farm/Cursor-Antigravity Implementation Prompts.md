# Cursor / Antigravity Implementation Prompts

These prompts are intentionally in English for coding agents.

Target existing codebase:

```text
D:\Development\Parsers\RedditScraper
```

## Prompt 1 - Project Audit And Refactor Plan

```text
You are working in an existing Python project at D:\Development\Parsers\RedditScraper.

Goal:
Turn this prototype Reddit/RSS scraper into a modular ContentFarm ingestion and drafting system for the AI/SaaS niche.

First, inspect the codebase:
- README.md
- sources.yaml
- database.py
- scraper.py
- rss_scraper.py
- main_orchestrator.py
- processor_drafts.py

Do not rewrite code yet.

Produce a refactor plan with:
1. Current architecture summary.
2. Main risks and bugs.
3. Proposed module layout.
4. Database migration plan.
5. Backward compatibility plan.
6. First 5 implementation tasks.

Constraints:
- Keep the current working scripts runnable during the refactor.
- Do not delete existing output files.
- Do not hardcode API keys.
- Keep MVP local-first: SQLite + Markdown exports.
```

## Prompt 2 - Database Schema Migration

```text
Implement a backward-compatible SQLite schema migration for D:\Development\Parsers\RedditScraper.

Problem:
The current `posts` table is too limited and `is_posted` mixes drafting and publishing state.

Add a migration system and create these tables:

1. source_items
- id TEXT PRIMARY KEY
- source_type TEXT
- source_name TEXT
- source_url TEXT
- canonical_url TEXT
- title TEXT
- body TEXT
- author TEXT
- published_at REAL
- collected_at REAL
- external_score REAL
- comments_count INTEGER
- language TEXT
- niche TEXT
- raw_payload_json TEXT
- content_hash TEXT
- status TEXT DEFAULT 'collected'

2. item_scores
- item_id TEXT PRIMARY KEY
- money_intent INTEGER
- pain_intensity INTEGER
- novelty INTEGER
- engagement_velocity INTEGER
- transformability INTEGER
- risk_score INTEGER
- total_score REAL
- reason TEXT
- scored_at REAL

3. content_drafts
- id TEXT PRIMARY KEY
- item_id TEXT
- target_language TEXT
- target_platform TEXT
- draft_text TEXT
- source_notes TEXT
- risk_flags TEXT
- status TEXT DEFAULT 'draft'
- created_at REAL

4. publishing_events
- id TEXT PRIMARY KEY
- draft_id TEXT
- platform TEXT
- status TEXT
- published_url TEXT
- metrics_json TEXT
- created_at REAL

Requirements:
- Keep the old `posts` table for compatibility.
- Add helper functions for insert/get/update on new tables.
- Add tests or a simple smoke script that initializes the DB and inserts one fake item.
- Use only standard library unless the project already uses a dependency.
```

## Prompt 3 - Source Registry Refactor

```text
Refactor sources.yaml into a flexible source registry for the AI/SaaS niche.

Current file contains finance, AI, and crypto mixed together.

Implement support for this structure:
- settings
- niches.ai_saas
- source groups: reddit, rss, hackernews, producthunt, github, x_api
- per-source fields: enabled, name, url/subreddit/topic, source_weight, fetch_interval_hours, notes
- keyword groups: core, buyer_intent, pain, launch, risk

Update config loader code so existing scripts can still read old fields if needed.

Create a new example file:
- sources.ai_saas.example.yaml

Do not put real tokens in YAML.
Use .env.example for token names only.
```

## Prompt 4 - Fetcher Interface

```text
Create a modular fetcher interface.

Add a package:

contentfarm/
  __init__.py
  fetchers/
    __init__.py
    base.py
    reddit_json.py
    rss.py
  models.py
  normalizer.py

Define a common SourceItem model using dataclasses or pydantic if already available.

Every fetcher should return a list of normalized SourceItem objects with:
- id
- source_type
- source_name
- source_url
- canonical_url
- title
- body
- author
- published_at
- external_score
- comments_count
- raw_payload
- niche

Refactor current scraper.py and rss_scraper.py logic into RedditJsonFetcher and RssFetcher.

Keep existing scraper.py runnable by calling the new modules.
```

## Prompt 5 - Hacker News And Product Hunt Fetchers

```text
Add two optional fetchers:

1. HackerNewsFetcher
- Uses official Hacker News Firebase API.
- Supports topstories, newstories, beststories, showstories, askstories.
- Fetches item details.
- Filters for AI/SaaS keywords.

2. ProductHuntFetcher
- Uses Product Hunt GraphQL API.
- Reads PRODUCTHUNT_TOKEN from environment.
- Disabled by default if token is missing.
- Adds a warning that Product Hunt API commercial use requires permission by default.

Requirements:
- Do not crash if optional API token is missing.
- Return normalized SourceItem objects.
- Add rate limiting/backoff.
- Add logging.
- Add a dry-run command that prints top 10 fetched items.
```

## Prompt 6 - Scoring Engine

```text
Implement a deterministic scoring engine for collected source items.

Create:
- contentfarm/scoring.py

Score dimensions:
- money_intent: 1-5
- pain_intensity: 1-5
- novelty: 1-5
- engagement_velocity: 1-5
- transformability: 1-5
- risk_score: 1-5

Total:
money_intent * 0.30
+ pain_intensity * 0.20
+ novelty * 0.15
+ engagement_velocity * 0.15
+ transformability * 0.10
+ monetization_fit * 0.10
- risk_score * 0.20

Use keyword rules first. Do not call an LLM in this task.

Output:
- score object
- short reason
- matched keyword groups

Add tests with sample AI/SaaS items.
```

## Prompt 7 - Obsidian Export Queue

```text
Implement an Obsidian exporter.

Target vault:
D:\Personal\myvault

Target project folder:
D:\Personal\myvault\Projects\Content Farm

Export top scored source items into:
Projects/Content Farm/experiments/YYYY-MM-DD AI-SaaS Opportunities.md

Each item should include:
- title
- source
- URL
- score
- reason
- risk flags
- suggested content formats
- checkbox for approval

Rules:
- Do not overwrite existing files unless --force is passed.
- Keep output in Russian.
- Include source links for review.
- Do not include full long scraped bodies unless explicitly requested.
```

## Prompt 8 - LLM Draft Generator

```text
Implement a draft generator that consumes approved source items and creates drafts.

Inputs:
- source item
- score object
- target language: ru or uk
- target platform: telegram, x, linkedin, instagram_reel, facebook_page

Outputs:
- draft_text
- source_notes
- risk_flags
- CTA suggestion
- image_or_video_prompt

Rules:
- Do not plagiarize the source.
- Do not invent facts.
- Always preserve source URL internally.
- If risk is high, output "research only" instead of a publishable draft.
- Do not generate medical, legal, investment, gambling, or crypto-trading advice.
- No autoposting.

Make the LLM provider pluggable:
- Gemini via GEMINI_API_KEY first, because the project already uses google-generativeai.
- Keep provider interface open for OpenAI/Anthropic later.
```

## Prompt 9 - Approval CLI

```text
Create a local CLI for the approval workflow.

Commands:
- collect
- score
- export-opportunities
- generate-drafts
- list-drafts
- approve-draft <id>
- reject-draft <id>
- mark-posted <id> --platform --url

No command should post to social media.

Store statuses in SQLite.
Export readable Markdown snapshots to Obsidian.
```

## Prompt 10 - Tests And Documentation

```text
Add basic tests and documentation.

Tests:
- DB migration smoke test
- source registry parsing test
- source item normalization test
- scoring test
- Obsidian export test using a temp folder

Docs:
- README update
- .env.example update
- sources.ai_saas.example.yaml
- "How to run MVP" section

Keep the docs concise and operational.
```

