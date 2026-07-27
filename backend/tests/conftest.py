"""
Shared pytest configuration.

The engine in db/session.py is a module-level singleton, so its pooled
connections bind to whichever event loop first used them. pytest-asyncio
creates a new loop per test by default, which leaves the second test holding
connections attached to a dead loop.

Fix: one session-scoped loop for the whole run. The alternative (disposing the
engine between tests) works but costs a full reconnect per test and hides
genuine pool bugs.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
