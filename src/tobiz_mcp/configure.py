"""Безопасный мастер первичной настройки tobiz-mcp."""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path


def project_ids(value: str) -> list[str]:
    result = list(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))
    invalid = [project_id for project_id in result if not project_id.isdigit()]
    if not result or invalid:
        detail = f": {', '.join(invalid)}" if invalid else ""
        raise argparse.ArgumentTypeError(f"project_id должен состоять из цифр{detail}")
    return result


def safe_env_value(value: str, name: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError(f"{name} не должен содержать переносы строк")
    return value


def env_text(*, projects: list[str], email: str = "", password: str = "",
             read_only: bool = False, transport: str = "stdio",
             http_token: str = "") -> str:
    lines = [
        "# Создано tobiz-mcp-configure. Не добавляйте этот файл в git.",
        f"TOBIZ_EMAIL={safe_env_value(email, 'email')}",
        f"TOBIZ_PASSWORD={safe_env_value(password, 'password')}",
        f"TOBIZ_READ_ONLY={'1' if read_only else '0'}",
        f"TOBIZ_ALLOWED_PROJECT_IDS={','.join(projects)}",
        "TOBIZ_REQUIRE_PROJECT_ALLOWLIST=true",
        "TOBIZ_MAX_UPLOAD_MB=10",
        f"MCP_TRANSPORT={transport}",
    ]
    if transport == "http":
        lines.extend([
            "MCP_HTTP_HOST=0.0.0.0",
            "MCP_HTTP_PORT=8765",
            f"MCP_HTTP_TOKEN={safe_env_value(http_token, 'http_token') or secrets.token_urlsafe(32)}",
        ])
    lines.append("TOBIZ_LOG_LEVEL=INFO")
    return "\n".join(lines) + "\n"


def write_config(path: Path, content: str) -> Path | None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_name(f"{path.name}.backup-{stamp}")
        suffix = 1
        while backup.exists():
            backup = path.with_name(f"{path.name}.backup-{stamp}-{suffix}")
            suffix += 1
        shutil.copy2(path, backup)
    path.write_text(content, encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)
    return backup


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="tobiz-mcp-configure",
        description="Создает безопасный .env с обязательным белым списком проектов.",
    )
    result.add_argument("--projects", type=project_ids,
                        help="Разрешенные project_id через запятую")
    result.add_argument("--output", type=Path, default=Path(".env"))
    result.add_argument("--email", default=None,
                        help="Логин TOBIZ; пароль запрашивается скрыто")
    result.add_argument("--read-only", action="store_true")
    result.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    result.add_argument("--non-interactive", action="store_true",
                        help="Брать логин и пароль из TOBIZ_EMAIL/TOBIZ_PASSWORD")
    return result


def main() -> None:
    args = parser().parse_args()
    projects = args.projects
    if projects is None:
        if args.non_interactive:
            raise SystemExit("--projects обязателен в неинтерактивном режиме")
        projects = project_ids(input("Разрешенные project_id через запятую: "))

    if args.non_interactive:
        email = os.environ.get("TOBIZ_EMAIL", "")
        password = os.environ.get("TOBIZ_PASSWORD", "")
    else:
        email = args.email if args.email is not None else input("Email TOBIZ (можно оставить пустым для готовой сессии): ").strip()
        password = getpass.getpass("Пароль TOBIZ (можно оставить пустым): ") if email else ""

    content = env_text(
        projects=projects,
        email=email,
        password=password,
        read_only=args.read_only,
        transport=args.transport,
    )
    backup = write_config(args.output, content)
    target = args.output.expanduser().resolve()
    print(f"Конфигурация создана: {target}")
    print(f"Разрешенные проекты: {', '.join(projects)}")
    print("Строгая изоляция: включена")
    if backup:
        print(f"Предыдущая конфигурация сохранена: {backup}")
    print("После подключения запустите tobiz_onboarding_check.")


if __name__ == "__main__":
    main()
