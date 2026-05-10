# Дорожная карта (функционал)

## Фрейм

Инструмент внутренний: цель — выпускать платные отчеты/выгрузки, а не строить SaaS.

Источник правды по текущему прогрессу: `marketplace-scraper/project.md`.

## Статус

- Phase 0 (стабилизация) ✅
- Phase 1 (business layer + project-rooted workflows) ✅

## Дальше

### Phase 2 — Каталог клиента (`project_products`)

- импорт из Excel
- валидация + отчет импорта
- дедупликация SKU

### Phase 3 — Набор мониторинга (`competitors`, `monitored_products`)

- быстрый флоу добавления ссылок конкурентов
- хранение статуса/последней проверки

### Phase 4 — Price Update (сбор `price_observations`)

- массовое обновление watchlist
- корректная обработка фейлов без потери связей

### Phase 5 — Price Audit (первый продаваемый)

- Excel: summary + raw observations + рекомендации по SKU
- метрики: min/avg/latest/delta, availability

### Phase 6 — Weekly мониторинг

- дельты, исчезновения/появления, приоритетный action list

### Phase 7 — AI summary (опционально)

- короткое резюме + предупреждения о пробелах данных
- сохранить в `report_runs.summary`

### Phase 8 — Контент карточек (опционально, high-margin)

- аудит карточек + генерация улучшенного текста/структуры
- версионирование в `generated_content`

### Phase 9 — CLI/расписание

- CLI команды для запуска отчетов
- расписание через Windows Task Scheduler

## Ближайшая последовательность

1) Phase 2: импорт каталога  
2) Phase 3: набор мониторинга  
3) Phase 4: сбор наблюдений  
4) Phase 5: первый Price Audit отчет  
