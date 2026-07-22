"""
backend/tunnel_state.py

Explicit finite-state machine for the Cloudflare Tunnel lifecycle.

Valid state graph:
  STOPPED -> INSTALLING -> STARTING -> CONNECTING -> CONNECTED
  CONNECTED -> DEGRADED -> CONNECTED           (self-heal)
  CONNECTED/DEGRADED -> STOPPING -> STOPPED
  CONNECTING/STARTING -> FAILED -> STOPPING -> STOPPED
  FAILED -> STARTING                           (retry loop)

Only the CONNECTED state is considered "ready" for URL exposure.
"""
from __future__ import annotations

import logging
import threading
from enum import Enum

logger = logging.getLogger("camz.tunnel.state")


class TunnelState(str, Enum):
    STOPPED = "STOPPED"
    INSTALLING = "INSTALLING"
    STARTING = "STARTING"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    STOPPING = "STOPPING"


# Valid transitions: {from_state: set_of_allowed_to_states}
_VALID_TRANSITIONS: dict[TunnelState, set[TunnelState]] = {
    TunnelState.STOPPED: {TunnelState.INSTALLING, TunnelState.STARTING, TunnelState.STOPPING},
    TunnelState.INSTALLING: {TunnelState.STARTING, TunnelState.FAILED, TunnelState.STOPPING, TunnelState.STOPPED},
    TunnelState.STARTING: {TunnelState.CONNECTING, TunnelState.FAILED, TunnelState.STOPPING, TunnelState.STOPPED},
    TunnelState.CONNECTING: {TunnelState.CONNECTED, TunnelState.FAILED, TunnelState.STOPPING, TunnelState.STOPPED},
    TunnelState.CONNECTED: {TunnelState.DEGRADED, TunnelState.FAILED, TunnelState.STOPPING, TunnelState.STOPPED},
    TunnelState.DEGRADED: {TunnelState.CONNECTED, TunnelState.FAILED, TunnelState.STOPPING, TunnelState.STOPPED},
    TunnelState.FAILED: {TunnelState.STARTING, TunnelState.STOPPING, TunnelState.STOPPED},
    TunnelState.STOPPING: {TunnelState.STOPPED},
}


class TunnelStateMachine:
    """Thread-safe state machine managing Cloudflare Tunnel lifecycle state transitions."""

    def __init__(self) -> None:
        self._state = TunnelState.STOPPED
        self._lock = threading.RLock()
        self._listeners: list = []

    @property
    def state(self) -> TunnelState:
        with self._lock:
            return self._state

    def is_connected(self) -> bool:
        return self.state == TunnelState.CONNECTED

    def is_active(self) -> bool:
        return self.state not in (TunnelState.STOPPED, TunnelState.FAILED)

    def transition(self, new_state: TunnelState, reason: str = "") -> bool:
        """Attempt a state transition, returning True if valid or False if rejected."""
        with self._lock:
            old_state = self._state
            allowed = _VALID_TRANSITIONS.get(old_state, set())

            if new_state == old_state:
                return True

            if new_state not in allowed:
                logger.warning(
                    "Tunnel: invalid transition %s -> %s ignored (reason=%s). Allowed: %s",
                    old_state.value, new_state.value, reason,
                    ", ".join(s.value for s in allowed),
                )
                return False

            self._state = new_state
            tag = f" [{reason}]" if reason else ""
            logger.info("Tunnel state: %s -> %s%s", old_state.value, new_state.value, tag)

            for cb in self._listeners:
                try:
                    cb(old_state, new_state, reason)
                except Exception as exc:
                    logger.debug("Tunnel state listener error: %s", exc)

            return True

    def add_listener(self, callback) -> None:
        """Register a state change callback signature (old_state, new_state, reason)."""
        with self._lock:
            self._listeners.append(callback)

    def force(self, new_state: TunnelState, reason: str = "") -> None:
        """Force a state transition overriding validity checks."""
        with self._lock:
            old_state = self._state
            self._state = new_state
            logger.warning(
                "Tunnel state FORCED: %s -> %s [%s]",
                old_state.value, new_state.value, reason,
            )
