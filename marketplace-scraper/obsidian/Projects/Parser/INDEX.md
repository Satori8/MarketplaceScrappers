# Parser

## Суть

Внутренний инструмент для производства платных отчетов/выгрузок по украинским маркетплейсам. Скрапер/GUI не продается — продается результат.

Код: `D:\Scrappers\marketplace-scraper`

## Текущее состояние

Источник правды: `marketplace-scraper/project.md`

- Stage 15 — Business Intelligence Layer & Project-Rooted Workflows ✅ (Phase 1 Complete)
- Все операции привязаны к `active_project_id`
- Режимы парсинга: Search / Filter(Category) / Seller(Store) / Price Update (watchlist)
- Business layer таблицы: `projects`, `project_products`, `competitors`, `monitored_products`, `price_observations`, `report_runs`

## Карточки проекта

- [[Report as a Service Strategy]]
- [[Implementation Roadmap]]
- [[Conversation Notes]]
- [[Cursor and Antigravity Prompts]]
- [[Marketpalce parser]]

## Ближайшие задачи (бизнес)

- [ ] Импорт каталога клиента из Excel в `project_products` (Phase 2)
- [ ] Быстрый флоу: discovery `products` → добавление в `project_products` → линковка `monitored_products`
- [ ] Первый продаваемый отчет: Price Audit (Excel) + рекомендации
- [ ] Weekly мониторинг (дельты/риски/action list)

## Риски

- `config.yaml` содержит реальные API keys (вынести в `.env`, сделать `.env.example`, ключи ротировать)
- Профили браузера могут содержать cookies/localStorage

## Короткие AI-команды (для планирования)

```text
Прочитай marketplace-scraper/project.md и эту заметку. Сформируй 5 ближайших задач (Phase 2–5) с критериями готовности.
```

```text
Проверь marketplace-scraper/config.yaml на секреты и предложи безопасную миграцию в .env + .env.example.
```
