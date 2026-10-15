# Changelog

## Unreleased

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
