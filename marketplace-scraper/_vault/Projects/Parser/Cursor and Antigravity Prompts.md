# Cursor and Antigravity Prompts

This note stores implementation prompts for the parser/reporting project.

Related notes:

- [[Report as a Service Strategy]]
- [[Implementation Roadmap]]

## Prompt 1: Reframe Project Around Internal Reporting Tool

```text
Reframe this project as an internal report generation tool, not software for resale.

Read project.md and the current codebase. Add or update documentation to reflect:
- the scraper is an internal operator tool;
- the sellable output is reports and analytics;
- GUI polish is secondary;
- repeatable report generation, stable DB, and export quality are primary.

Do not change business logic yet. Create or update markdown documentation only.
```

## Prompt 2: Stabilize Current Scraper

```text
Проанализируй проект как senior Python engineer. Прочитай project.md, core, db, gui, scrapers.
Нужно подготовить проект к превращению во внутренний инструмент для производства отчетов по украинским маркетплейсам.

Сначала не делай больших рефакторингов. Исправь только критические баги из project.md, которые мешают стабильной работе:
B1, B2, B3, B6, B9, B10, B12, B13, B14, B19, B20.

Требования:
- не ломать существующий GUI;
- сохранить текущий workflow запуска через main.py;
- добавить минимальные тесты или smoke-тесты там, где возможно;
- после изменений перечислить файлы, что изменил, и как проверить.
```

## Prompt 3: Add Business Database Schema

```text
Add business-level SQLite tables for report-as-a-service workflows:
clients, client_products, competitors, monitored_products, price_observations, report_runs, content_templates, generated_content.

Requirements:
- keep existing products and price_history tables;
- migrations must be idempotent;
- do not destroy existing data;
- add repository classes for clients, client products, monitoring, and report runs;
- add basic smoke tests for schema initialization.
```

## Prompt 4: Import Client Catalog

```text
Implement client catalog import from Excel.

The operator should be able to import a customer's product list with:
- SKU;
- title;
- current selling price;
- cost price if available;
- marketplace;
- product URL;
- category;
- brand/model if available.

Save imported rows into client_products.
Add validation and an import summary:
- rows imported;
- rows skipped;
- missing required fields;
- duplicate SKUs.
```

## Prompt 5: Add Competitor Monitoring Set

```text
Implement monitored competitor products.

The operator should be able to attach competitor product URLs to a client product.
Save them into monitored_products.
On manual monitoring run:
- detect marketplace from URL;
- use existing scraper detail-page logic where possible;
- save price, availability, title, raw JSON into price_observations.

Do not use price_history for this business monitoring layer.
```

## Prompt 6: Parse Specific Competitor Store

```text
Добавь возможность парсить конкретный магазин/продавца и сохранять его товары.

Сценарий:
- пользователь добавляет competitor: name, marketplace, seller_url;
- запускает scrape competitor;
- приложение получает список товаров продавца, цены, URL, наличие;
- сохраняет найденные товары как competitor catalog snapshot;
- пользователь может выбрать, какие товары добавить в monitored_products.

Если для marketplace нет готового способа парсить страницу продавца, сделай интерфейс и заглушку с понятной ошибкой.
Начни с Prom.ua, если текущий scraper позволяет.
```

## Prompt 7: Generate Price Audit Report

```text
Implement a Price Audit Excel report for a client.

Report should include:
- client SKU;
- client title;
- client own price;
- monitored competitor URL;
- latest competitor price;
- min competitor price per client product;
- avg competitor price per client product;
- difference UAH;
- difference percent;
- recommendation: lower, raise, hold, check manually.

Use openpyxl.
Create a separate exporter, do not break existing ExcelExporter.
```

## Prompt 8: Add Weekly Monitoring Report

```text
Implement a Weekly Monitoring Excel report.

Compare latest price observations against observations from 7 days ago or nearest available previous point.

Include:
- price increases;
- price decreases;
- competitors that became unavailable;
- competitors that reappeared;
- products where client's price became uncompetitive;
- stale links with no successful check.
```

## Prompt 9: Add AI Summary for Reports

```text
Add AI-generated executive summary for report outputs.

Input:
- computed report metrics;
- top price changes;
- top risks;
- top opportunities.

Output:
- short Ukrainian or Russian summary for the business owner;
- action list for manager;
- no fake certainty;
- mention data gaps if scraping failed.

Save summary into report_runs.summary and include it in Excel Summary sheet.
```

## Prompt 10: AI Product Content Generation

```text
Добавь модуль AI-генерации контента для товаров.

Нужно:
- таблица content_templates;
- таблица generated_content;
- CRUD шаблонов промптов;
- переменные в шаблонах: title, brand, model, specs, category, marketplace, keywords;
- генерация title, short_description, full_description, specs_json;
- возможность выбрать marketplace: Prom.ua, Rozetka, Хорошоп, Generic;
- результат сохранять версионно, не перезаписывать старый.

Используй существующий GeminiClient.
Добавь окно GUI: Content Generator.
```

## Prompt 12: Excel Analytics with Charts

```text
Улучши Excel export.

Добавь экспорт:
1. Price Monitoring Report
2. Competitor Report

Используй openpyxl.
Добавь:
- автоширину колонок;
- цветовые статусы;
- лист Summary;
- графики динамики цены по выбранным товарам;
- отдельный лист Raw Observations.

Не ломай существующий ExcelExporter, лучше добавь новый AnalyticsExcelExporter.
```

## Prompt 13: CLI and Scheduler

```text
Добавь CLI-режим для запуска без GUI.

Команды:
- python main.py gui
- python main.py monitor --client-id 1
- python main.py analytics-excel --client-id 1 --out report.xlsx
- python main.py generate-content --client-id 1 --marketplace prom

Добавь простой scheduler, который можно запускать вручную или через Windows Task Scheduler.
GUI должен остаться рабочим.
```

## Prompt 14: Client Installation Hygiene

```text
Подготовь проект к установке и регулярному локальному использованию.

Нужно:
- .env.example или config.example.yaml без ключей;
- requirements cleanup;
- README для установки на Windows;
- команда создания БД;
- команда запуска GUI;
- инструкция для Playwright install;
- базовая структура папок output/reports/feeds/logs;
- не коммитить credentials и реальные ключи.
```
