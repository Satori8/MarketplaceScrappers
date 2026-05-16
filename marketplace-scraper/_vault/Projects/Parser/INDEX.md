# Parser

## Суть

Внутренний инструмент для производства платных отчетов по украинским маркетплейсам. Скрапер/GUI не продается — продается результат.

Код: `D:\Scrappers\marketplace-scraper`

## Текущее состояние

Источник правды: `marketplace-scraper/project.md`

- **Phase 2.5 — Modular Async MAPI Scraper Architecture ✅ (Завершено, стабилизировано)**
- **Phase 4 — MAPI GUI Integration ✅ (Завершено, стабилизировано)**
  - Интеграция `scrapers/mapi_scraper` как движка, расширение DB, GUI polish.
  - [x] Создан профессиональный **Portfolio README.md** с архитектурой и product-контекстом.
- **Phase 5 — Global Intelligence & Reports 🔄 (В работе)**
  - Первый продаваемый отчет: Price Audit (Excel) + рекомендации
  - Тестирование интеграции → проектный дашборд

## Карточки проекта

- [[Report as a Service Strategy]]
- [[Implementation Roadmap]]
- [[Cursor and Antigravity Prompts]]

## Ближайшие задачи

- [ ] **АКТИВНО: Интеграция MAPI в GUI** — заменить playwright-вызовы на mapi_scraper, fallback остается
- [ ] Тестирование интеграции GUI + MAPI
- [ ] Проектный дашборд
- [ ] Первый продаваемый отчет: Price Audit (Excel) + рекомендации
- [ ] Weekly мониторинг (дельты/риски/action list)

## Контекст (коротко)

- Скрапер не продукт; продукт — отчеты/аналитика/выгрузки/рекомендации.
- Приоритет: повторяемость, история, качество отчетов.
- Не приоритет: SaaS-аккаунты, биллинг, внешний "красивый" продукт.

## Технические заметки

- [x] Основной парсинг переведен на MAPI (curl_cffi + async). Playwright — fallback.
- [x] Модульная структура `scrapers/mapi_scraper/sites/` для каждого маркетплейса.
- [x] Нормализация: общая схема `id, sku, price, name, avail_code, merchant_name, url, properties[]`
- [ ] Интеграция MAPI в GUI workflows — В РАБОТЕ
- [ ] `config.yaml` содержит реальные API keys. Требует миграции в `.env`!

## Риски

- `config.yaml` содержит реальные API keys. Требует ближайшей миграции!
- профили браузера/fallback могут накапливать мусор, нужны сбросы.
