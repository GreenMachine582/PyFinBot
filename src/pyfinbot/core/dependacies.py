from __future__ import annotations

from typing import Optional

from fastapi import Header


# --- Dependency to read X-User-ID header (optional) ---
async def x_user_id_dep(x_user_id: Optional[str] = Header(default=None, alias="X-User-ID")) -> Optional[str]:
    return x_user_id
