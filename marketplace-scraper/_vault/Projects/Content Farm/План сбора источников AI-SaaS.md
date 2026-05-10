# План сбора источников AI/SaaS

## Цель

Собирать ранние сигналы из англоязычных источников, которые можно превратить в полезный русско- и украиноязычный контент.

Не цель:

- копировать чужие посты;
- массово парсить всё подряд;
- обходить антибот-защиту;
- автопостить без контроля.

## Source Tiers

### Tier 1: обязательные источники MVP

Самые простые и полезные для первого цикла:

1. Reddit
2. RSS официальных блогов и AI/SaaS медиа
3. Hacker News official API
4. Product Hunt API
5. GitHub API / releases / trending-like monitoring

### Tier 2: добавить после MVP

- X API
- YouTube transcripts
- newsletters
- SaaS changelog pages
- job posts / hiring signals
- podcast transcripts

### Tier 3: только после доказанной ценности

- платные social listening API;
- коммерческие data providers;
- собственные crawler workers;
- browser automation для сайтов без API.

## Reddit Sources

### Core SaaS / founder pain

- r/SaaS
- r/startups
- r/Entrepreneur
- r/smallbusiness
- r/SideProject
- r/indiehackers
- r/ProductManagement
- r/sales
- r/marketing
- r/growmybusiness

### AI tools / builders

- r/OpenAI
- r/ChatGPT
- r/ClaudeAI
- r/LocalLLaMA
- r/ArtificialInteligence
- r/AI_Agents
- r/AItools
- r/PromptEngineering
- r/n8n
- r/automation
- r/selfhosted

### What to extract

- pain points;
- repeated complaints;
- tool recommendations;
- failed attempts;
- pricing complaints;
- launch feedback;
- workflow screenshots/descriptions;
- "what tool should I use" questions;
- "I built X" posts.

### Reddit filters

Separate filters by intent:

#### Pain

Markers:

- "struggling with"
- "is there a tool"
- "how do you manage"
- "wasting time"
- "manual process"
- "can't find"
- "too expensive"
- "alternatives to"

#### Buyer intent

Markers:

- "best tool"
- "recommend"
- "looking for"
- "which software"
- "switching from"
- "pricing"
- "integrations"

#### Founder/market signal

Markers:

- "launched"
- "built"
- "mrr"
- "waitlist"
- "users"
- "churn"
- "acquisition"
- "growth"

## RSS Sources

### Official AI/provider feeds

Start with sources already in `sources.yaml`, then clean and expand:

- OpenAI blog/news
- Anthropic news
- Google DeepMind blog
- Google AI Developers blog
- Meta AI blog
- Hugging Face blog
- NVIDIA blog
- Microsoft AI / Azure AI blog
- LangChain blog
- LlamaIndex blog
- Vercel AI / product blog
- Cloudflare AI / Workers AI blog

### AI/SaaS media

- TechCrunch AI
- VentureBeat AI
- The Decoder
- MIT News AI
- KDnuggets
- Latent Space
- Ben's Bites
- TLDR AI
- The Rundown AI

### What to extract

- product launches;
- API changes;
- pricing changes;
- model releases;
- funding/acquisitions;
- security incidents;
- benchmark claims;
- integrations;
- open-source releases.

## Hacker News

Use official HN Firebase API.

Endpoints to use:

- `/v0/topstories`
- `/v0/newstories`
- `/v0/beststories`
- `/v0/showstories`
- `/v0/askstories`
- `/v0/item/<id>`

Filters:

- title contains AI/SaaS/tool/productivity/dev keywords;
- URL domain is relevant;
- score/comment count velocity;
- comments contain repeated pain signals.

Good content formats:

- "HN обсуждает..."
- "Почему разработчики спорят о..."
- "Новая open-source альтернатива..."
- "Сигнал: людям не хватает..."

## Product Hunt

Use official Product Hunt API carefully.

Important:

- Product Hunt API docs say commercial use is not allowed by default without contacting them.
- For MVP, use it as research/source discovery, not as a commercial data product.

Collect:

- product name;
- tagline;
- topics;
- votes;
- comments;
- makers;
- launch date;
- website URL.

Filters:

- AI;
- productivity;
- automation;
- sales;
- marketing;
- analytics;
- devtools;
- no-code;
- customer support;
- content creation.

Good content formats:

- "5 новых AI tools за неделю"
- "что запускают на Product Hunt"
- "какие SaaS появляются вокруг боли X"

## GitHub

Use GitHub API where possible.

Collect:

- new repositories by topic;
- stars velocity;
- releases;
- changelogs;
- issues with repeated pain;
- README positioning.

Topics:

- ai-agent
- llm
- rag
- automation
- n8n
- workflow-automation
- saas
- crm
- sales-automation
- customer-support
- analytics
- scraping

Good content formats:

- "open-source tool of the day"
- "GitHub repo растёт: почему"
- "идея сервиса на основе issue pain"

## X/Twitter

Do not scrape with browser automation.

Use only:

- official API;
- manual lists;
- exports from approved tools;
- embedded/manual review workflow.

For MVP:

- keep X as output channel and manual research source;
- do not build X ingestion until Reddit/RSS/HN/Product Hunt are working.

## Source Registry Schema

Suggested `sources.yaml` structure:

```yaml
settings:
  timezone: Europe/Kiev
  default_language_targets: [ru, uk]
  min_signal_score: 60

niches:
  ai_saas:
    enabled: true
    description: "AI tools, B2B SaaS, automation, productivity, devtools"
    keywords:
      core: [ai, llm, saas, automation, workflow, agent, productivity]
      buyer_intent: ["best tool", "alternative", "pricing", "recommend", "integrations"]
      pain: ["manual", "too expensive", "struggling", "can't find", "wasting time"]
    reddit:
      enabled: true
      subreddits:
        - SaaS
        - startups
        - Entrepreneur
        - smallbusiness
        - OpenAI
        - ChatGPT
        - LocalLLaMA
        - AI_Agents
        - n8n
        - automation
    rss:
      enabled: true
      feeds:
        - name: OpenAI
          url: "..."
          source_weight: 0.9
        - name: Anthropic
          url: "..."
          source_weight: 0.9
    hackernews:
      enabled: true
      feeds: [topstories, newstories, showstories, askstories]
    producthunt:
      enabled: false
      reason: "needs API token and commercial-use review"
```

## Daily Collection Routine

1. Fetch new source items.
2. Normalize into DB.
3. Deduplicate by canonical URL + content hash.
4. Score.
5. Export top 20 to Obsidian.
6. Generate 5-10 drafts.
7. Manually approve 1-3.
8. Publish manually or schedule.
9. Record metrics.

