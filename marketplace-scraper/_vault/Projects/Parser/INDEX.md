# Parser

## Суть

Внутренний инструмент для производства платных отчетов по украинским маркетплейсам. Скрапер/GUI не продается — продается результат.

Код: `D:\Scrappers\marketplace-scraper`

## Текущее состояние

Источник правды: `marketplace-scraper/project.md`

- **Phase 2.5 — Modular Async MAPI Scraper Architecture ✅ (Завершено, стабилизировано)**
- Построен модульный скрапер на базе `curl_cffi` с поддержкой асинхронных запросов (`async_scrape_url`) и потокобезопасной локализацией состояния (пагинации). Резиновая модульная структура `scrapers/mapi_scraper`.
- Внедрены потоковые запросы через `asyncio.gather` с проксированием к `Rozetka`, `Prom`, `Allo`, `Epicentr`.
- **Rozetka:** Внедрен 3-уровневый парсинг (Direct API → LD+JSON → rz-client-state). Асинхронные HTTP-запросы извлекают данные страницами с автоматической переборкой товарных ID.
- **Prom.ua:** GraphQL (поиск, бренды, категории, продавцы) перенесен на асинхронный пайплайн в обход WAF.
- **Allo:** Извлечение SSR и исполнение `execjs` безопасно обернуто в `run_in_executor` во избежание блокировок event loop.
- **Epicentr:** Stateless API вызовы v1 и v2 с поддержкой async.
- Этап нормализации поддерживает асинхронный и потокобезопасный `normalize(raw_data)`.
- **Stage 15 — Business Intelligence Layer & Project-Rooted Workflows ✅ (Завершено ранее).**
- Все операции привязаны к `active_project_id`.

## Карточки проекта

- [[Report as a Service Strategy]]
- [[Implementation Roadmap]]
- [[Cursor and Antigravity Prompts]]

## Ближайшие задачи

- [ ] rozetka - seller 3 fast api requests instead of parsing
- [ ] Первый продаваемый отчет: Price Audit (Excel) + рекомендации
- [ ] Weekly мониторинг (дельты/риски/action list)

## Контекст (коротко)

- Скрапер не продукт; продукт — отчеты/аналитика/выгрузки/рекомендации.
- Приоритет: повторяемость, история, качество отчетов.
- Не приоритет: SaaS-аккаунты, биллинг, внешний “красивый” продукт.

## Технические заметки

- [x] Основной парсинг переведен на JSON API и SSR извлечение (curl_cffi), UI/Selenium остается как fallback.
- [x] Фильтр «нет в наличии».
- [ ] Интегрировать Fast Scraper API в основные GUI workflows "Category", "Search" и "Price Update".

## Риски

- `config.yaml` содержит реальные API keys. Требует ближайшей миграции!
- профили браузера/fallback могут накапливать мусор, нужны сбросы.

## Короткие AI-команды (планирование)

```text
Прочитай marketplace-scraper/project.md и эту заметку. Начни работу над Phase 2 (Каталог клиента): реализуй импорт каталога из Excel в таблицу project_products с валидацией колонок.
```

```text
Перенеси чувствительные данные из config.yaml в .env, обнови логику загрузки конфигурации в приложении и создай шаблон .env.example.
```
