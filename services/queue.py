"""Queue utilities for background processing."""
from __future__ import annotations

import os
from redis import Redis
from rq import Queue


DEFAULT_REDIS_URL = "redis://redis:6379/0"
DEFAULT_QUEUE_NAME = "ktufy"


def get_queue() -> Queue:
    redis_url = os.getenv("REDIS_URL", DEFAULT_REDIS_URL)
    return Queue(DEFAULT_QUEUE_NAME, connection=Redis.from_url(redis_url))
