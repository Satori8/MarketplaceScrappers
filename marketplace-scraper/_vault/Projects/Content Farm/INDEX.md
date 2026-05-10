# Content Farm

## Objective

Build a semi-automated content intelligence and publishing system.

Core idea:

> Parse foreign resources, detect high-value topics, transform them into platform-native social content, and publish through controlled automation.

This is not a spam farm. The target system should behave like an editorial desk with automation:

```text
sources -> extraction -> scoring -> editorial angle -> content packages -> approval -> scheduled posting -> feedback loop
```

## Why This Project Fits

This project combines existing strengths:

- Python automation
- scraping/parsing
- marketplace/data normalization
- AI prompt systems
- YouTube/social content production
- n8n/Docker workflows
- Obsidian as project memory

## External Folders

- `D:\Scrappers\marketplace-scraper` - useful scraper architecture reference.
- `D:\Development\Parsers` - parser experiments.
- `D:\n8n_data` - automation workflows.
- `D:\Work\Active\Ecommerce` - related scraping/data shortcuts.
- `D:\Development\SileroTTS` - content production pipeline reference.

## Core Notes

- [[Аудит плана и улучшения]]
- [[Strategy]]
- [[Architecture]]
- [[Domain Map]]
- [[MVP Plan]]
- [[Source List]]
- [[План сбора источников AI-SaaS]]
- [[Risk Policy]]
- [[Content Formats]]
- [[Metrics]]
- [[Как нагнать аудиторию]]
- [[Языковая стратегия]]
- [[Монетизация]]
- [[Instagram и Facebook]]
- [[Официальные API и ограничения]]
- [[Cursor-Antigravity Implementation Prompts]]
- [[Инструменты и ИИ для генерации контента]]
- [[Draft Generator Prompt]]

## First Version

Do not start with all platforms and all niches.

MVP:

1. Pick 1 money domain.
2. Pick 2 source types.
3. Pick 1 output platform.
4. Generate drafts only.
5. Human approval before posting.
6. Measure conversion/engagement.

Recommended first test:

- Domain: AI tools / B2B SaaS
- Sources: Reddit + RSS + Hacker News + Product Hunt/GitHub where API access is acceptable
- Output: X/Twitter threads + Telegram posts
- Monetization: affiliate links, lead magnets, service funnel

Updated technical direction:

- Reuse `D:\Development\Parsers\RedditScraper`.
- Refactor it into modular fetchers and a local approval queue.
- Do not build direct autoposting before source scoring and draft quality are proven.

## Current Tasks

- [ ] Choose first domain.
- [ ] Build source list for first domain.
- [ ] Define scoring model.
- [ ] Create draft generator prompt.
- [ ] Build no-posting MVP: collect -> score -> draft -> save to Obsidian.
- [ ] Add approval queue before any auto-posting.
- [ ] Decide platform order: Telegram, X, LinkedIn, YouTube Shorts, TikTok.
- [ ] Refactor `RedditScraper` into modular ContentFarm ingestion.
- [ ] Add Hacker News and Product Hunt/GitHub source modules.
- [ ] Replace `is_posted` with proper draft/publish statuses.

## Decisions

- Start with drafts and approval, not full autopost.
- Prefer content-driven niches over regulated high-risk niches at first.
- Treat automation as distribution and research assist, not fake engagement.
- Obsidian stores strategy, decisions, source lists, prompt registry, and weekly reviews.

## Open Questions

- Which language first inside each channel: Ukrainian, Russian, or separate channels?
- Is monetization via affiliate, services, lead generation, newsletter, communities, or owned products?
- Will accounts be personal brands, faceless brands, or niche media pages?
- What is the minimum acceptable manual review step?
