"""CLI: python -m app.cli maintenance"""

import asyncio
import sys

from sqlalchemy import text

from app.db.session import get_session_factory
from app.services.maintenance import run_maintenance


async def cmd_maintenance() -> None:
    async with get_session_factory()() as session:
        # Jalankan sebagai superadmin agar mencakup semua tenant.
        await session.execute(text("SELECT set_config('app.is_superadmin', 'on', false)"))
        await session.execute(text("SELECT set_config('app.user_id', '', false)"))
        await session.execute(text("SELECT set_config('app.tenant_id', '', false)"))
        result = await run_maintenance(session)
        await session.commit()
        print(f"Maintenance selesai: {result}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in {"maintenance"}:
        print("Penggunaan: python -m app.cli maintenance")
        sys.exit(2)
    asyncio.run(cmd_maintenance())


if __name__ == "__main__":
    main()
