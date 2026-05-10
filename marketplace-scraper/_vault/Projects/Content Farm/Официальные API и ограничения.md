# Официальные API и ограничения

## Зачем эта заметка

Контент-ферма должна строиться на источниках, которые можно стабильно собирать.

Главная ошибка - начинать с браузерного scraping X/Meta или массового автопостинга. Это может быстро привести к банам аккаунтов и потере всей инфраструктуры.

## Reddit

Использовать осторожно.

Важные моменты:

- у Reddit есть Developer Terms и Data API Terms;
- доступ к API может меняться, ограничиваться или прекращаться;
- при использовании Reddit API нужны attribution и соблюдение правил;
- при прекращении доступа могут быть требования по удалению cached/stored user content.

Практический вывод:

- для MVP можно использовать Reddit как source intelligence;
- хранить source URL и минимум нужного текста;
- не строить коммерческий продукт только на Reddit без понимания Data API Terms;
- не делать автокомменты/авто-DM.

## X / Twitter

X прямо запрещает non-API automation вроде scripting website/browser automation.

Практический вывод:

- не писать browser bot для X;
- X ingestion только через официальный API или ручные списки/экспорты;
- X posting только через официальный API или вручную;
- не автоматизировать unsolicited replies/DM.

## Product Hunt

Product Hunt API даёт GraphQL-доступ и developer token.

Важно:

- по документации Product Hunt API по умолчанию не должен использоваться для коммерческих целей без контакта с Product Hunt;
- использовать как research в MVP осторожно;
- не перепродавать/не строить коммерческий data product на их данных без разрешения.

## Hacker News

HN official Firebase API удобен для MVP.

Подходит для:

- top stories;
- new stories;
- show/ask stories;
- item details;
- comments tree.

Практический вывод:

- хороший стабильный источник для AI/SaaS/devtools сигналов;
- не требует сложной авторизации;
- read-only source intelligence.

## GitHub

GitHub API подходит для:

- repository search;
- releases;
- issues;
- topics;
- updated repositories.

Практический вывод:

- использовать как источник open-source и devtools сигналов;
- не путать stars с реальным demand;
- смотреть issues/comments как источник pain signals.

## Meta / Instagram / Facebook

Meta Terms запрещают automated access/collection без разрешения.

Практический вывод:

- не использовать Instagram/Facebook как scraping source;
- использовать как publishing channels;
- стартовать с Meta Business Suite;
- API подключать позже и официально.

## Ссылки

- Reddit Data API Terms: https://redditinc.com/policies/data-api-terms
- Reddit Developer Terms: https://redditinc.com/policies/developer-terms
- X Automation Rules: https://help.x.com/en/rules-and-policies/x-automation
- X Developer Guidelines: https://docs.x.com/developer-guidelines
- Hacker News official API: https://github.com/HackerNews/API
- Product Hunt API docs: https://www.producthunt.com/v2/docs
- GitHub REST API docs: https://docs.github.com/en/rest
- Meta Terms: https://www.facebook.com/terms
- Instagram Content Publishing docs: https://developers.facebook.com/docs/instagram-api/guides/content-publishing

