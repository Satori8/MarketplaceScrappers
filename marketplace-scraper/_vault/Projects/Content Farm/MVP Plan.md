# MVP Plan

## Goal

Validate whether scraped foreign source intelligence can reliably produce useful social content drafts in one niche.

Use existing parser code instead of starting from zero:

```text
D:\Development\Parsers\RedditScraper
```

## MVP Scope

Domain:

- AI tools / B2B SaaS

Languages:

- Russian
- Ukrainian

Sources:

- Reddit
- RSS/newsletters/blogs
- Hacker News
- Product Hunt / GitHub, if access is acceptable

Output:

- X thread draft
- Telegram post draft
- LinkedIn post draft
- Instagram/Facebook short video caption draft
- Ukrainian/Russian adapted versions for approved winners

No automatic posting in v1.

## Week 1

- [ ] Audit `D:\Development\Parsers\RedditScraper`.
- [ ] Create `D:\ContentFarm` only for data exports if needed.
- [ ] Create `sources.ai_saas.example.yaml`.
- [ ] Add 20 Reddit communities and 30 RSS/blog sources.
- [ ] Add Hacker News source plan.
- [ ] Add Product Hunt/GitHub source plan.
- [ ] Build RSS fetcher.
- [ ] Build Reddit fetcher.
- [ ] Store raw items as JSONL.
- [ ] Decide primary language for first 30 days.

## Week 2

- [ ] Deduplicate items.
- [ ] Build scoring model.
- [ ] Generate daily top 20 opportunities.
- [ ] Export shortlist to Obsidian.
- [ ] Manually inspect whether scores make sense.
- [ ] Replace fake RSS upvotes with proper source weights.
- [ ] Split statuses: collected, selected, drafted, approved, posted.

## Week 3

- [ ] Build content draft generator.
- [ ] Add source citation block to every draft.
- [ ] Add risk flags.
- [ ] Create approval queue.
- [ ] Publish manually from approved drafts.
- [ ] Add Instagram/Facebook draft format, but publish manually or through Meta Business Suite.

## Week 4

- [ ] Track post results.
- [ ] Build feedback loop: source -> draft -> post -> metrics.
- [ ] Decide whether to add auto-scheduling.
- [ ] Decide whether to expand to second domain.

## Success Criteria

Minimum:

- 100+ source items collected per day.
- 10+ useful content opportunities per day.
- 3+ publishable drafts per day.
- Manual review under 30 minutes per day.

Strong signal:

- Posts get saves/bookmarks/comments.
- Some posts drive clicks.
- Repeated source categories produce good results.
- You can see a product/service offer emerging.
