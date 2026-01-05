#!/usr/bin/env python3
"""
Скрипт для ручного запуска миграций базы данных.

Использование:
    python scripts/run_migrations.py
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from migrations.migration_manager import run_migrations  # noqa: E402


async def main():
    """Запускает миграции."""
    print("=" * 60)
    print("ЗАПУСК МИГРАЦИЙ БАЗЫ ДАННЫХ")
    print("=" * 60)

    try:
        await run_migrations()
        print("\n" + "=" * 60)
        print("✅ МИГРАЦИИ ЗАВЕРШЕНЫ УСПЕШНО")
        print("=" * 60)
        return 0
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ МИГРАЦИЙ: {e}")
        print("=" * 60)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
