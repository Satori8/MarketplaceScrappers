# Parser

## Суть

Внутренний инструмент для производства платных отчетов по украинским маркетплейсам. Скрапер/GUI не продается — продается результат.

Код: `D:\Scrappers\marketplace-scraper`

## Текущее состояние

Источник правды: `marketplace-scraper/project.md`

- **Phase 1.5 — Fast Scraper API & Normalization ✅ (Завершено, стабилизировано)**
- Построен быстрый модуль `fast_api/fast_scraper.py` на базе `curl_cffi` (обход Cloudflare).
- **Rozetka:** Внедрен 3-уровневый парсинг (Direct API → LD+JSON → rz-client-state), покрывающий поиск, категории и поддомены (auto/rztk).
- **Prom.ua:** Успешно отреверсен неавторизованный GraphQL API (поиск, бренды, категории, продавцы) в обход сессий и WAF. Найдены корректные endpoint'ы и схема пагинации.
- **Allo:** Извлечение SSR через `execjs`.
- **Hotline:** Начата интеграция (структура и регистрация класса).
- Реализована универсальная нормализация (`fast_api/normalizer.py`), сводящая любой результат в единую JSON-схему (цена, наличие, характеристики, id/sku).
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
