# Parser

## Суть

Внутренний инструмент для производства платных отчетов по украинским маркетплейсам. Скрапер/GUI не продается — продается результат.

Код: `D:\Scrappers\marketplace-scraper`

## Текущее состояние

Источник правды: `marketplace-scraper/project.md`

- Stage 15 — Business Intelligence Layer & Project-Rooted Workflows ✅ (Phase 1 Complete)
- все операции привязаны к `active_project_id`
- режимы парсинга: Search / Filter(Category) / Seller(Store) / Price Update (watchlist)
- business layer: `projects`, `project_products`, `competitors`, `monitored_products`, `price_observations`, `report_runs`

## Карточки проекта

- [[Report as a Service Strategy]]
- [[Implementation Roadmap]]
- [[Cursor and Antigravity Prompts]]

## Ближайшие задачи

- [ ] Импорт каталога из Excel в `project_products` (Phase 2)
- [ ] Быстрый флоу: discovery `products` → `project_products` → `monitored_products`
- [ ] Первый продаваемый отчет: Price Audit (Excel) + рекомендации
- [ ] Weekly мониторинг (дельты/риски/action list)
- [ ] Убрать реальные ключи из `config.yaml`, вынести в `.env`, сделать `.env.example`, ключи ротировать

## Контекст (коротко)

- Скрапер не продукт; продукт — отчеты/аналитика/выгрузки/рекомендации.
- Приоритет: повторяемость, история, качество отчетов.
- Не приоритет: SaaS-аккаунты, биллинг, внешний “красивый” продукт.

## Технические заметки

- [ ] По возможности переходить на JSON-парсинг.
- [x] Фильтр «нет в наличии».
- [ ] Протестировать Filter/Category страницы.

## Риски

- `config.yaml` содержит реальные API keys
- профили браузера могут содержать cookies/localStorage

## Короткие AI-команды (планирование)

```text
Прочитай marketplace-scraper/project.md и эту заметку. Сформируй 5 ближайших задач (Phase 2–5) с критериями готовности.
```

```text
Проверь marketplace-scraper/config.yaml на секреты и предложи безопасную миграцию в .env + .env.example.
```
