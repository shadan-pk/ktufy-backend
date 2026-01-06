"""Active user tracking (in-memory).

Tracks recently-seen authenticated users based on requests that use `get_current_user`.
This is intended for the admin dashboard "currently logged-in users" panel.

Note: This is per-process memory; in multi-worker deployments you'll want a shared store.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional


@dataclass
class ActiveUser:
    user_id: str
    email: str
    role: str
    last_seen: datetime

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "role": self.role,
            "last_seen": self.last_seen.isoformat(),
        }


class ActiveUserTracker:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._users: Dict[str, ActiveUser] = {}

    async def record(self, *, user_id: str, email: str, role: str = "authenticated") -> None:
        now = datetime.utcnow()
        async with self._lock:
            self._users[user_id] = ActiveUser(
                user_id=user_id,
                email=email or "",
                role=role or "authenticated",
                last_seen=now,
            )

    async def get_active(self, *, window_seconds: int = 600) -> List[ActiveUser]:
        cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
        async with self._lock:
            # prune stale
            stale_ids = [uid for uid, u in self._users.items() if u.last_seen < cutoff]
            for uid in stale_ids:
                self._users.pop(uid, None)

            return sorted(self._users.values(), key=lambda u: u.last_seen, reverse=True)


active_user_tracker = ActiveUserTracker()
