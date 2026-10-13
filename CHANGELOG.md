# Changelog

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
