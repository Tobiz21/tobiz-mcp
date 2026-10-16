# Changelog

- Пакетная публикация проверяет источник каждого изображения до записи; варианты нового товара
  могут ссылаться на еще не загруженное фото через `image_index`, который безопасно преобразуется
  в штатный `image_id` после загрузки галереи.
- Добавлен `tobiz_release_project_gate`: единый релизный вердикт учитывает все страницы проекта,
  статьи, товары и варианты; обязательный блог или каталог нельзя сдать пустым.
- Добавлены `tobiz_publish_article_package` и `tobiz_publish_product_package`: полный пакет сначала
  проходит dry-run preflight, затем создается атомарно вместе с категориями, изображениями и
  вариантами; неполная сущность удаляется при ошибке или провале итогового аудита.

## Unreleased

- Добавлены read-only аудиты готовности статей и товаров к публикации: содержательность,
  структура, SEO, изображения, категории, цены, видео и уникальность вариантов.
- Добавлены предзаписные гейты полного пакета статьи и товара, чтобы не создавать пустые
  сущности до проверки текста, SEO, категорий, будущих изображений и вариантов.
- Добавлен аудит многостраничного проекта: уникальность URL и SEO, качество композиции каждой
  видимой страницы, единые типы шапки и подвала, обязательный CTA или контактный выход.
- Добавлен исполняемый release-контракт из четырех контрольных сценариев: лендинг,
  многостраничный сайт, SEO-статья с медиа и каталог товаров с вариантами.
- Добавлен единый планировщик многостраничного сайта: проверяет одну главную, уникальные маршруты,
  короткое общее меню, назначение каждой страницы, готовность брифа и единый визуальный язык.
- Добавлен возобновляемый многостраничный пакет: отдельный штатный пакет каждой страницы,
  общая навигация и единый статус готовности без создания частичного сайта в TOBIZ.
- Добавлена транзакционная сборка многостраничного пакета: общий preflight навигации и страниц,
  preview, откат созданных страниц при сбое и итоговый аудит всего проекта.
- Добавлен evidence-first гейт брифа: MCP задает минимальный набор недостающих вопросов и
  блокирует качественную сборку без подтвержденных фактов, сохраняя явный режим прототипа.
- Заглушки вроде «уточнить», «клиент исправит», example.com и демонстрационного телефона TOBIZ
  больше не считаются подтвержденными фактами, включая значения внутри списков и объектов.
- Добавлен goal-specific гейт архитектуры: подбор предпочитает шаблоны с критическими секциями,
  достаточными слоями доверия и композицией не ниже 7/10; неполная структура блокирует quality build.
- Добавлен контракт конверсионного пути: до копирования проверяются штатная форма, требуемые поля,
  кнопка отправки и порядок «Имя» перед «Телефоном»; подходящие шаблоны получают приоритет.
- План фиксирует штатные якоря исходного шаблона, а preflight блокирует внутренние ссылки на
  несуществующие секции до копирования страницы.
- Recipe preflight сверяет штатные кнопки с согласованным `primary_cta` и блокирует нейтральную
  замену целевого действия в quality-режиме.
- SEO preflight семантически сверяет метаданные с подтвержденной темой и регионом брифа,
  учитывая распространенные русские словоформы.
- Усилен media preflight: фотослоты несут смысл секции и тип кадра, требуют визуального
  подтверждения соответствия, конкретного описания сюжета и запрещают повтор файла между секциями.
- Media preflight теперь также запрещает повтор одного файла внутри группы карточек или галереи.
- Загрузчик добавляет SHA-256 фактических байтов в `media_asset`, а preflight распознает один кадр,
  повторно загруженный под разными именами.
- Добавлена прослеживаемость «бриф → текст»: каждый подтвержденный факт связывается через
  `evidence_codes` с конкретным штатным слотом, а пропущенные и неизвестные связи блокируют сборку.
- Связь `evidence_codes` теперь засчитывается только при наличии в тексте смыслового фрагмента
  подтвержденного факта; учтены распространенные русские словоформы.
- Evidence preflight проверяет смысловую роль секции и блокирует формальное размещение факта в
  неподходящем блоке, например экспертности в контактах.
- `tobiz_validate_site_recipe` теперь включает доказательность текста в собственный
  `ready_for_build`, поэтому ранняя проверка больше не выдает ложный успешный вердикт.
- Добавлен anti-duplication гейт текста: одинаковые содержательные заголовки и абзацы в разных
  секциях блокируют quality-сборку, не затрагивая повторяемые кнопки и служебные подписи.
- Явные текстовые заглушки (`Lorem ipsum`, «Заголовок», `TODO` и подобные) больше не считаются
  готовым наполнением recipe в quality-режиме.
- Сильный разброс длины текстов соседних карточек теперь блокирует quality-сборку; в режиме
  прототипа он остается предупреждением для последующей штатной настройки выравнивания.
- Мобильные лимиты кнопок и заголовков стали обязательным quality-гейтом; умеренное превышение
  длины обычного абзаца остается рекомендацией, а не механическим запретом.
- Паспорт блока теперь различает подписи и кнопку внутри штатного массива формы по полю `type`:
  CTA формы участвует в конверсионных проверках, а подписи не искажают аудит заголовков.
- Конверсионный preflight блокирует каждую штатную форму без подписанной кнопки отправки и формы
  с повторяющимися смысловыми полями, даже если на странице уже есть другая исправная форма.
- Согласованный `primary_cta` теперь требует явного заполнения хотя бы одной штатной кнопки в
  recipe; повторяющиеся подписи полей формы исключены из проверки дублированного текста секций.
- Конверсионный контракт требует обязательный телефон или email: форму, отправляемую без контакта,
  quality-сборка блокирует как `contact_field_not_required`.
- Добавлен гейт читаемости формы: каждое видимое поле требует видимый заголовок или placeholder;
  безымянные поля блокируются как `form_field_unlabeled`.
- Обязательные поля формы теперь сверяются с брифом: незаказанные обязательные вопросы блокируются
  как `unexpected_required_form_fields`, а дополнительные необязательные поля остаются допустимы.
- Конверсионный аудит рекурсивно находит штатные `formN` во вложенных моделях, включая Flex, и
  возвращает точный `form_path` в диагностике.
- Editor roundtrip теперь использует тот же рекурсивный поиск и предупреждает о вложенной форме
  без кнопки, включая штатный тип `submit` при определении корректной отправки.
- Форма с полями, но без submit-кнопки переведена из предупреждения в структурный блокер:
  `tobiz_editor_roundtrip_check` возвращает `save_blocked` и `editor_safe=false`.
- Добавлен однокомандный `tobiz_start_site`: он без лишних запросов возвращает вопросы к брифу
  либо подбирает и проверяет шаблон, сохраняет чистый пакет и сообщает один следующий шаг.
- Добавлена read-only проверка актуальности паспортов установленной библиотеки шаблонов.
- Добавлено локальное безопасное хранение структурированной дизайнерской обратной связи.
- Выбор шаблона и конвейер сборки теперь учитывают накопленные оценки с ограниченным весом,
  сохраняя исходное объяснение и не позволяя одному отзыву полностью изменить решение.
- Известные типизированные проблемы шаблона формируют anti-regression профиль и при повторном
  обнаружении переводят итоговую приемку сборки в `save_blocked`.
- Планирование и сборка блокируют копирование изменившегося шаблона до ручной проверки и
  обновления его паспорта.
- Добавлено preview-first локальное обновление паспорта эталона без редактирования исходного
  проекта и без выпуска новой версии MCP.
- Пользователь может зарегистрировать проверенную страницу своего аккаунта как локальный шаблон;
  это устраняет обязательную зависимость библиотеки от исходного аккаунта разработчика.
- Регистрация локального шаблона теперь блокируется без editor-safe проверки, композиции 7/10,
  чистого адаптивного аудита и явного визуального подтверждения снимков.
- Подбор, планирование и сборка автоматически пропускают недоступные или устаревшие источники и
  используют следующий подходящий проверенный шаблон текущего аккаунта.
- Preflight источников выполняется с ограниченной параллельностью три запроса для ускорения первой
  сборки без агрессивной нагрузки на TOBIZ.
- Добавлен read-only поиск страниц-кандидатов для локальной библиотеки по структуре, композиции,
  доле Flex и безопасности штатного редактора.

- Версия подготовлена как `0.9.0-beta.3`; публичные manifest и container workflow синхронизированы.
- Финальный release gate теперь может выдать `ready` только при наличии эталона, проверки редактора,
  аудита фактов и явного визуального подтверждения скриншотов.
- Копирование блока получило preflight зависимостей: дубли anchor, отсутствующие внутренние цели и
  ссылки на сущности проекта обнаруживаются до создания блока.
- Добавлена инвентаризация реальных Flex-схем страницы для постепенного формирования проверенного
  корпуса вместо догадок о полях конструктора.
- Аварийная сборка автоматически удаляет только что созданную неполную страницу.
- Добавлен еженедельный opt-in live-contract workflow для настоящего тестового проекта TOBIZ.
- CI дополнительно компилирует весь Python-код и проверяет целостность зависимостей.
- Добавлены безопасные инспекция и обновление нативных Flex-блоков `1600` с optimistic lock.
- Flex перед сохранением проверяется на поддерживаемые элементы, дубли ID, мобильную геометрию,
  наложения, некорректные размеры и минимальную зону CTA; HTML/cache по-прежнему формирует TOBIZ.
- Добавлено безопасное копирование проверенного нативного блока между страницами и проектами без
  реконструкции его полей; доступны preview, hash-защита и отдельный Flex-preflight.
- Финальная приемка теперь обязательно проверяет desktop, tablet 800px и mobile.
- Штатная шапка перед hero больше не дает ложный `weak_first_screen`; закрепление учитывается отдельно.
- Добавлены проверки служебного текста, соседних фотофонов и случайной полосатости секций.
- Lazy-load изображений дожидается загрузки; закрытый FAQ и overlay-подписи не считаются обрезанием.
- Фотоплан получил смысловые роли кадров, а аудит - осторожную сверку фото с ближайшим текстом.
- Минимальная зона нажатия CTA на планшете и мобильном увеличена до 44x44px.
- Добавлен `tobiz_create_project` для полного сценария нового сайта без ручного создания проекта.
- Сборка теперь запрещает отсутствующий целевой проект и запись в проект исходного шаблона.
- Служебные названия страниц очищаются от символов, которые панель TOBIZ не принимает.
- Нативные select и числовые настройки принимают значения вроде `4` и `55px` и нормализуются.
- Медиапакет каталога больше не требует скрытые дополнительные изображения карточек.
- Тематика мероприятий и квестов выделена отдельно и не смешивается со строительством.

## 0.9.0b2

- Added semantic page-composition audit with goal-specific coverage, trust and section-order scoring.
- Added native reference comparison for structure, section roles, block styles and rendered design profiles.
- Added a unified design release gate covering rendered QA, composition, reference fidelity,
  editor safety and unsaved draft detection.
- Added rendered image composition auditing with source/rendered geometry, crop and resolution
  checks, cross-section reuse detection, background-text scrim validation and semantic context.
- Clean-install verification now continues against the signed public GHCR image when the external
  MCP Registry times out, while still failing on an incorrect Registry record.
- Added deterministic native site planning with stable plan IDs, section purposes, copy limits,
  photo briefs and post-build conformance checks integrated into the quality-page pipeline.
- Added an evidence-bound content compiler that maps client facts to native template slots, reports
  missing proof before copywriting and prevents fabricated prices, reviews, credentials and guarantees.
- Added a brief-bound factual claim audit for phone numbers, email addresses, prices, discounts,
  experience, durations and numeric results; unsupported claims now block the unified release gate.
- Added pre-copy recipe validation for native structure, meaningful slot coverage, mobile copy limits,
  card balance, contextual CTAs and brief-bound factual claims.
- Added pre-copy media-recipe validation for exact native image coverage, resolution, orientation,
  background text-safe areas, consistent card ratios, placeholders and cross-section reuse.
- Added a unified pre-copy build gate for plan identity, copy, factual claims, media, SEO, page slug
  and unsafe links, and wired the same verdict into the quality-page builder.
- Added one-call clean site-package scaffolding with exact copy, media and SEO fields while omitting
  all source-template copy to prevent accidental topic leakage.
- Added direct preview/build from the filled site package with schema, plan and template identity
  verification before the shared preflight and native one-save pipeline.
- Image uploads now return byte-verified PNG, JPEG, GIF, WebP and SVG dimensions, aspect ratio,
  content type and a ready-to-use media-recipe asset instead of relying on agent-supplied geometry.
- Added previewable batch media upload for complete site packages: native template block indexes are
  resolved safely and byte-verified image metadata is written back without changing block values.
- Added safe batch filling for exact package copy and SEO slots with duplicate/unknown target rejection,
  mobile-length warnings, factual validation and an immediate complete-package preflight.
- Added resumable site-package status with exact copy/media/SEO completion, missing slot coordinates,
  grouped blocker codes and one deterministic next action for any MCP client.
- Added atomic local site-package checkpoints with list/load tools and live plan/template revalidation,
  allowing work to continue safely after MCP reconnects or across different AI clients.
- Site package preparation, copy filling and applied media upload now checkpoint automatically; optional
  opt-out remains available, and explicit confirmed deletion provides local data lifecycle control.
- Package checkpoints now retain up to 20 content-addressed previous versions, avoid duplicate revisions,
  and support confirmed restoration while preserving the displaced current version.
- Added optimistic checkpoint concurrency: stale AI clients can no longer silently overwrite a newer
  package, while normal prepare/load/content/media flows propagate the content hash automatically.
- Added page-wide design-system analysis and safe native refinement with regression rollback.
- Added resilient official Registry verification to the clean-install release gate.
- Added a public multi-architecture GHCR image.
- Added a validated `server.json` and GitHub OIDC publishing to the official MCP Registry.
- Fixed public repository links and distribution checks.
- Added security guidance for support requests and shared installations.

## 0.9.0b1

- Добавлена защита от конфликтов между MCP и визуальным редактором.
- Чистые черновики автоматически перечитываются из TOBIZ.
- Перед сохранением создаются локальные резервные копии с безопасным восстановлением.
- Добавлены строгая изоляция проектов и фильтрация списка проектов.
- Добавлены мастер конфигурации и `tobiz_onboarding_check`.
- Добавлена приемка `tobiz-mcp-selftest --release`.
- Добавлена локальная диагностика без удаленной телеметрии и пользовательского контента.
