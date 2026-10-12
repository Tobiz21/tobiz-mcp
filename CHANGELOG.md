# Changelog

## 0.9.0b2

- Added semantic page-composition audit with goal-specific coverage, trust and section-order scoring.
- Added native reference comparison for structure, section roles, block styles and rendered design profiles.
- Added a unified design release gate covering rendered QA, composition, reference fidelity,
  editor safety and unsaved draft detection.
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
