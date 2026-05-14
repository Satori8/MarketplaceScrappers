# Дорожная карта (функционал)

Фрейм: инструмент внутренний, продукт — отчеты/выгрузки.

Источник правды по прогрессу: `marketplace-scraper/project.md`.

## Статус

- Phase 0 (стабилизация) ✅
- Phase 1 (business layer + project-rooted workflows) ✅
- Phase 1.5 (Fast Scraper API: curl_cffi, bypass CF, normalization & ExecJS) ✅

## Дальше

### Phase 2 — Каталог клиента (`project_products`) (В работе)

- импорт из Excel
- валидация + отчет импорта
- дедупликация SKU

### Phase 3 — Мониторинг (`competitors`, `monitored_products`)

- быстрый флоу добавления конкурентов/URL из результатов Discovery
- статус/последняя проверка

### Phase 4 — High-Speed API Integration (Частично)

- заменить медленные Selenium/Playwright скраперы в основном GUI на интегрированный `fast_api`.
- массовое независимое параллельное обновление watchlist (`price_observations`).

### Phase 5 — Price Audit (первый продаваемый)

- Excel: summary + raw data + рекомендации по SKU
- метрики: min/avg/latest/delta, availability

### Phase 6 — Weekly мониторинг

- дельты, исчезновения/появления, priority action list

### Phase 7 — AI summary (опционально)

- резюме + предупреждения о пробелах данных
- сохранить в `report_runs.summary`

### Phase 8 — Контент карточек (опционально)

- аудит карточек + улучшенный текст/структура
- версионирование в `generated_content`

### Phase 9 — CLI/расписание (потом)

- CLI команды для запуска отчетов
- расписание через Windows Task Scheduler
