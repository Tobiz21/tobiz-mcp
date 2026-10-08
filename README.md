# tobiz-mcp

MCP-сервер для конструктора сайтов **TOBIZ**: даёт агенту (Hermes, Codex, OpenCode и любому
MCP-клиенту) читать и менять сайты — проекты, страницы, блоки, изображения.

## Выбор дизайна

- `tobiz_design_library` возвращает паспорта девяти установленных штатных шаблонов и семнадцати
  визуальных референсов: исходные страницы, сильные стороны, плотность, зависимость от фото и долю Flex.
- `tobiz_select_design` ранжирует установленные шаблоны по брифу до копирования страницы и
  объясняет выбор, риски и подходящие визуальные референсы.
- `tobiz_editor_roundtrip_check` без сохранения собирает штатный payload редактора и заранее
  выявляет блоки, из-за которых ручное пересохранение может изменить или сломать страницу.
- `tobiz_build_quality_page` выбирает проверенный шаблон по брифу, соблюдает лимит Flex 30%,
  выдает компактный рецепт и медиаплан, сохраняет копию один раз и завершает desktop/mobile и
  editor-safe проверками. Полный технический паспорт возвращается только при `details=true`.

## Быстрый старт

```bash
git clone git@github.com:raydev-ru/tobiz-mcp.git && cd tobiz-mcp
docker build -t tobiz-mcp .
docker run --rm -it --entrypoint tobiz-mcp-configure \
  -v "$PWD:/config" tobiz-mcp --projects 123456,123457 --output /config/.env
```

Мастер скрыто запросит пароль, включит строгую изоляцию и разрешит MCP работать только с
перечисленными проектами. Если `.env` уже существует, рядом останется резервная копия. Для
автоматической установки передайте логин и пароль через окружение и добавьте
`--non-interactive`; пароль не передавайте аргументом командной строки.

Проверка, что сервер видит конструктор (логин/сессия и рендерер):

```bash
docker run --rm --entrypoint tobiz-mcp-selftest --env-file .env \
  -v tobiz-session:/data/session -v tobiz-assets:/data/assets \
  tobiz-mcp --health
```

Ожидаемый ответ — JSON, где `session.present: true` и `renderer_available: true`. Если логин по
паролю аккаунт не пропускает (встречается капча), положите свою сессию в том — см.
«Полезно знать» ниже.

Дальше достаточно подключить сервер к своему агенту — он запускает образ сам, как stdio-сервер.

## Подключение к агенту

Подставьте свой абсолютный путь к `.env`. Образ запускается с `-i` (stdio) — больше ничего не нужно.

**Hermes**

```bash
hermes mcp add tobiz --command docker --args run -i --rm \
  --env-file /путь/до/tobiz-mcp2/.env \
  -v tobiz-session:/data/session -v tobiz-assets:/data/assets \
  tobiz-mcp
hermes mcp test tobiz
```

**Codex** (`~/.codex/config.toml`)

```toml
[mcp_servers.tobiz]
command = "docker"
args = ["run", "-i", "--rm", "--env-file", "/путь/до/tobiz-mcp2/.env",
        "-v", "tobiz-session:/data/session", "-v", "tobiz-assets:/data/assets", "tobiz-mcp"]
startup_timeout_sec = 30
tool_timeout_sec = 180
```

**OpenCode** (`opencode.json`)

```json
{"mcp": {"servers": {"tobiz": {"type": "local",
  "command": ["docker", "run", "-i", "--rm", "--env-file", "/путь/до/tobiz-mcp2/.env",
              "-v", "tobiz-session:/data/session", "-v", "tobiz-assets:/data/assets", "tobiz-mcp"]}}}}
```

Инструменты появятся с префиксом сервера — например `mcp__tobiz__tobiz_list_projects`.

Загрузка картинок работает через файлы: положите изображение в локальный каталог и смонтируйте
его как `/data/inbox`, тогда путь к файлу передаётся в `tobiz_upload_image` (либо сразу
`content_base64`, без монтирования).

## Два режима работы

MCP — это JSON-RPC, а не REST, и клиент подключается к серверу одним из двух способов:

| | **stdio** (по умолчанию) | **HTTP** (streamable HTTP) |
| --- | --- | --- |
| Кто запускает контейнер | клиент-агент сам: `docker run -i --rm …` | вы, один раз: `docker run -d …` |
| Сколько контейнеров | один на сессию агента, живёт до её конца | один постоянный, обслуживает всех |
| Кому подходит | Hermes / Codex / OpenCode на этой машине | клиенты по сети, несколько агентов, отладка через curl |
| Черновик правок | свой у каждого агента | общий на всех клиентов |

Контейнер запускается **не на каждую команду**: он один на сессию, а вызовы инструментов идут в него
потоком JSON-RPC (в stdio — через stdin/stdout). Черновик правок и кеш библиотеки блоков живут в
процессе, cookie-сессия — на томе, поэтому переживает перезапуск контейнера.

Постоянный HTTP-сервис:

```bash
docker run -d --name tobiz-mcp --restart unless-stopped -p 8765:8765 \
  -e MCP_TRANSPORT=http -e MCP_HTTP_TOKEN=секрет --env-file .env \
  -v tobiz-session:/data/session -v tobiz-assets:/data/assets tobiz-mcp
# endpoint: http://<хост>:8765/mcp, заголовок Authorization: Bearer секрет
```

Цена общего сервиса: черновик один на процесс — несколько агентов на одной странице будут мешать
друг другу. Для параллельной работы удобнее stdio: у каждого агента свой контейнер и свой черновик.

## Инструкции для агента (скил)

Инструменты — половина дела: агенту нужно знать порядок работы, грабли вендора и как проверять
результат. Это лежит в скиле [`skills/tobiz-mcp/SKILL.md`](skills/tobiz-mcp/SKILL.md).

**Hermes** — скил лежит в репозитории, вместе со справочниками (каталог блоков, движок, компоненты,
эндпоинты). Копируй папку целиком:

```bash
git clone https://github.com/raydev-ru/tobiz-mcp.git /tmp/tobiz-mcp
cp -r /tmp/tobiz-mcp/skills/tobiz-mcp ~/.hermes/skills/
```

Установка по прямой ссылке (`hermes skills install <raw-URL на SKILL.md>`) тоже работает, но
приносит только `SKILL.md` — без справочников и рецептов.

**Codex / OpenCode** читают [`AGENTS.md`](AGENTS.md) из корня репозитория автоматически; если
работаете не из репозитория — скопируйте файл в свой конфиг (`~/.codex/AGENTS.md` и аналоги).

В скиле: что пишется сразу, а что только по `tobiz_save_page`; 15 проверенных грабель (радиус
кнопок в `em` и вендорский CSS 2px, автоконтраст текста в формах, обязательный `block_id` при
загрузке картинок, отстающий `window.tobiz`, `?v=` = id страницы) и короткие рецепты под типовые
задачи.

## Инструменты

| Инструмент | Что делает |
| --- | --- |
| `tobiz_login`, `tobiz_session_status`, `tobiz_health` | вход, состояние сессии, диагностика |
| `tobiz_onboarding_check`, `tobiz_diagnostics` | готовность установки и локальный обезличенный отчет поддержки |
| `tobiz_list_projects` | проекты (сайты) аккаунта |
| `tobiz_list_pages` | страницы проекта |
| `tobiz_page_summary` | компактная карта страницы: порядок блоков, короткий текст, SEO-подсказка |
| `tobiz_list_blocks`, `tobiz_get_block` | блоки страницы и значения полей блока |
| `tobiz_page_info` | параметры страницы как в панели: название, URL, SEO, og:image, доступ |
| `tobiz_search_blocks`, `tobiz_describe_block` | поиск по библиотеке блоков, схема полей типа |
| `tobiz_block_controls` | реестр галочек и списков каждого типа: подписи, поля, дефолты, зависимости и варианты |
| `tobiz_audit_catalog` | аудит всех типов, галочек, списков, серверных значений и flex-вариантов |
| `tobiz_get_site_styles`, `tobiz_update_site_styles` | штатные глобальные шрифты, размеры, насыщенность и цвета кнопок через `page_config` |
| `tobiz_get_computed_styles`, `tobiz_screenshot_page` | реальные стили и полностраничные desktop/mobile PNG-снимки |
| `tobiz_diagnose_interactions`, `tobiz_audit_page`, `tobiz_audit_summary` | формы, попапы, кнопки, ссылки, контраст, геометрия, остатки исходной тематики, JS-ошибки и изображения |
| `tobiz_add_block`, `tobiz_update_block`, `tobiz_delete_block`, `tobiz_move_block` | правки черновика |
| `tobiz_save_page` | запись блоков на сайт: рендер HTML, SaveBlocks, проверка вёрстки |
| `tobiz_update_page` | правка параметров страницы (SEO, название, slug, og:image) — пишет сразу |
| `tobiz_copy_page` | копия страницы вместе с блоками в тот же или другой проект |
| `tobiz_build_from_template` | один конвейер: проверка рецепта, копирование, заполнение, одно сохранение, SEO и desktop/mobile-аудит |
| `tobiz_delete_page` | удаление страницы (требует `confirm=true`) |
| `tobiz_discard_changes`, `tobiz_verify_page` | откат черновика, проверка публичной вёрстки |
| `tobiz_upload_image`, `tobiz_set_block_image` | загрузка изображения и подстановка в поле |
| `tobiz_refresh_assets` | перекачать библиотеку блоков проекта |
| `tobiz_list_articles`, `tobiz_get_article`, `tobiz_create_article`, `tobiz_update_article`, `tobiz_delete_article` | штатный редактор статей: тексты, URL, SEO, публикация, категории |
| `tobiz_upload_article_image`, `tobiz_sort_article_images`, `tobiz_list_article_categories` | изображения, их порядок и категории статей |
| `tobiz_list_products`, `tobiz_get_product`, `tobiz_create_product`, `tobiz_update_product`, `tobiz_delete_product` | управление товарами: цены, остатки, метки, размеры, SEO и видео |
| `tobiz_upload_product_image`, `tobiz_sort_product_images`, `tobiz_list_product_categories` | галерея, порядок фото и категории товаров |
| `tobiz_list_product_offers`, `tobiz_get_product_offer`, `tobiz_create_product_offer`, `tobiz_update_product_offer`, `tobiz_delete_product_offer` | варианты товара: название, артикул, цена, остаток и фото |

Ответ инструмента: `{"ok": true, "data": {...}}` либо
`{"ok": false, "error": {"code": "...", "message": "...", "hint": "..."}}`.

## Как это устроено (коротко)

Редактор TOBIZ хранит не «значения полей», а готовый HTML блока, поэтому сервер рендерит этот HTML
сам — Node с шаблонами и хелперами вендора внутри образа. Правки **блоков** копятся в черновике в
памяти сервера и уходят на сайт только по явному `tobiz_save_page`.

Параметры самой страницы (название, URL, SEO, картинка для соцсетей) живут не в черновике, а в
панели конструктора: `tobiz_update_page` читает форму страницы, подменяет указанные поля и
отправляет её целиком — такое изменение видно на сайте сразу. Копирование и удаление страницы
(`tobiz_copy_page`, `tobiz_delete_page`) тоже применяются немедленно.

Статьи и товары также редактируются отдельными штатными модулями TOBIZ и применяются сразу, без
`tobiz_save_page`. Текст статьи принимает HTML CKEditor: изображения загружаются в ее галерею,
а видео вставляется штатным `iframe`. В товаре доступны три поля видео (`video1`-`video3`) и
штатные варианты (offers). Глобальные стили страницы хранятся в `page_config`: их правки попадают
в черновик и применяются через `tobiz_save_page`, как обычные блоки.

## Полезно знать

* **Блоки** не меняются без `tobiz_save_page`; `tobiz_update_page`, `tobiz_copy_page` и
  `tobiz_delete_page` пишут на сайт сразу — проверяйте `project_id`/`page_id` перед вызовом.
* `tobiz_update_page` отправляет всю форму страницы (как редактор), поэтому не переданные поля
  сохраняются как были — SEO можно править, не затирая название и slug.
* `tobiz_delete_page` требует `confirm=true`: без него вернётся отказ с названием страницы.
* Для экспериментов заведите отдельный сайт и `TOBIZ_READ_ONLY=1`.
* Если аккаунт требует капчу при входе, сервис вернёт `AUTH_CAPTCHA`. Тогда положите свою сессию
  в том — хватит двух cookie `session` и `email`:

  ```bash
  # cookies.json = {"session": "...", "email": "..."}
  docker run --rm -u 0 --entrypoint sh -v tobiz-session:/data -v "$PWD:/seed:ro" \
    tobiz-mcp -c 'cp /seed/cookies.json /data/session/ && chown -R 10001:10001 /data/session'
  ```

  После этого `TOBIZ_EMAIL`/`TOBIZ_PASSWORD` в `.env` можно оставить пустыми.
* `tobiz_upload_image` требует `block_id` реального блока страницы (без него конструктор отвечает
  «Изображение не загружено! #2»).
* Секреты не логируются: в журнал попадают только имена cookie.

## Переменные окружения

| Переменная | Назначение |
| --- | --- |
| `TOBIZ_EMAIL`, `TOBIZ_PASSWORD` | вход в конструктор (не нужны, если положена сессия) |
| `TOBIZ_READ_ONLY` | `1` — только чтение, инструменты правки не регистрируются |
| `TOBIZ_ALLOWED_PROJECT_IDS` | CSV со списком разрешённых `project_id`; пусто - все проекты аккаунта, если строгий режим выключен |
| `TOBIZ_REQUIRE_PROJECT_ALLOWLIST` | `true` запрещает работу с проектами, пока не заполнен `TOBIZ_ALLOWED_PROJECT_IDS`; рекомендуется для общей и клиентской установки |
| `TOBIZ_MAX_UPLOAD_MB` | лимит файла изображения (по умолчанию 10) |
| `MCP_TRANSPORT` | `stdio` (по умолчанию) или `http` |
| `MCP_HTTP_PORT`, `MCP_HTTP_TOKEN` | порт и токен для HTTP-транспорта |

После подключения запустите `tobiz_onboarding_check`. Для личной тестовой установки достаточно
`ready=true`; перед передачей другим пользователям требуется `distribution_ready=true`. Если передать
`project_id` и `page_id`, инструмент также проверит безопасное пересохранение страницы в редакторе,
не изменяя сайт.

Финальная приемка перед выдачей установки пользователю:

```bash
docker run --rm --entrypoint tobiz-mcp-selftest --env-file .env \
  -v tobiz-session:/data/session -v tobiz-assets:/data/assets -v tobiz-audit:/data/audit \
  tobiz-mcp --release PAGE_ID --project PROJECT_ID
```

Команда возвращает код `0` только при `release_ready=true`; отчет печатается в JSON и подходит для CI.
| `TOBIZ_LOG_LEVEL` | `INFO` по умолчанию, `WARNING` — тише |
