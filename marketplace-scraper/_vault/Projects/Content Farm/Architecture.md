# Architecture

## Pipeline

```text
Source Discovery
  -> Ingestion
  -> Cleaning
  -> Deduplication
  -> Topic Clustering
  -> Value Scoring
  -> Angle Selection
  -> Content Drafting
  -> Compliance Check
  -> Human Approval
  -> Scheduling / Posting
  -> Metrics Feedback
```

## Current Starting Point

Use the existing parser project as the codebase foundation:

```text
D:\Development\Parsers\RedditScraper
```

Existing useful parts:

- `sources.yaml`
- `scraper.py`
- `rss_scraper.py`
- `database.py`
- `main_orchestrator.py`
- `processor_drafts.py`
- `content_vault.db`

Main refactor:

```text
prototype scripts -> modular fetchers -> normalized source_items -> scoring -> Obsidian approval queue
```

## Modules

### 1. Source Discovery

Inputs:

- Reddit subreddits
- X/Twitter lists/search
- RSS feeds
- niche blogs
- newsletters
- Product Hunt / launches
- YouTube transcripts
- competitor social accounts

Output:

- source registry
- fetch schedule
- source quality score

### 2. Ingestion

Fetch raw items:

- title
- text
- URL
- author/source
- timestamp
- engagement metrics
- comments if available
- language

Store raw data before AI processing.

### 3. Cleaning

Remove:

- duplicates
- low-quality spam
- reposts
- obvious ads
- unsupported claims
- personal data where not needed

### 4. Scoring

Score each item:

- money intent
- novelty
- pain intensity
- engagement velocity
- content transformability
- affiliate/service fit
- risk level

Example:

```text
score = money_intent * 0.30
      + pain_intensity * 0.20
      + novelty * 0.15
      + engagement_velocity * 0.15
      + transformability * 0.10
      + monetization_fit * 0.10
      - risk_penalty
```

### 5. Draft Generation

Generate platform-specific drafts:

- X thread
- Telegram post
- LinkedIn post
- short video script
- newsletter block
- SEO article outline

### 6. Approval Queue

No direct auto-posting in MVP.

Each draft gets:

- source links
- generated draft
- risk flags
- proposed CTA
- status: draft / approved / rejected / posted

### 7. Publishing

Only after approval:

- schedule post
- post through official APIs/tools where possible
- record post URL
- track results

## Storage

Suggested local structure:

```text
D:\ContentFarm
  \data
    \raw
    \processed
    \drafts
    \approved
    \posted
  \configs
  \logs
  \exports
```

Obsidian stores strategy and decisions, not raw scraped dumps.

## Required Data Model Improvement

The current single `posts` table is not enough.

Add:

- `source_items`
- `item_scores`
- `content_drafts`
- `publishing_events`

Important status distinction:

```text
collected != selected != drafted != approved != posted
```

## First Technical Build

Python MVP:

- refactor current `sources.yaml`
- `contentfarm/fetchers/reddit_json.py`
- `contentfarm/fetchers/rss.py`
- `contentfarm/fetchers/hackernews.py`
- `contentfarm/fetchers/producthunt.py`
- `contentfarm/fetchers/github.py`
- `contentfarm/scoring.py`
- `contentfarm/drafts.py`
- `contentfarm/export_obsidian.py`

Later:

- n8n scheduler
- database
- web dashboard
- auto-poster
