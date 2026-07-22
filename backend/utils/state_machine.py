from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.utils.event_bus import EventBus

logger = logging.getLogger("camz.state")


class AppState(str, Enum):
    INITIALIZING = "INITIALIZING"
    VERIFYING = "VERIFYING"
    STARTING = "STARTING"
    READY = "READY"
    RECORDING = "RECORDING"
    RECOVERING = "RECOVERING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class ApplicationStateMachine:
    """Manages the current global operational state of the CAMZ application."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._state = AppState.INITIALIZING
        self._lock = threading.Lock()
        self._event_bus = event_bus

        self._valid_transitions = {
            AppState.INITIALIZING: [AppState.VERIFYING, AppState.STARTING, AppState.FAILED],
            AppState.VERIFYING: [AppState.STARTING, AppState.FAILED],
            AppState.STARTING: [AppState.READY, AppState.FAILED],
            AppState.READY: [AppState.RECORDING, AppState.RECOVERING, AppState.STOPPING, AppState.FAILED],
            AppState.RECORDING: [AppState.READY, AppState.RECOVERING, AppState.STOPPING, AppState.FAILED],
            AppState.RECOVERING: [AppState.READY, AppState.RECORDING, AppState.FAILED, AppState.STOPPING],
            AppState.STOPPING: [AppState.INITIALIZING, AppState.FAILED],
            AppState.FAILED: [AppState.INITIALIZING, AppState.STOPPING],
        }

    @property
    def current_state(self) -> AppState:
        with self._lock:
            return self._state

    def transition_to(self, new_state: AppState, reason: str = "") -> bool:
        """Atomically transition application state if allowed by valid transitions map."""
        with self._lock:
            old_state = self._state
            if new_state == old_state:
                return True

            is_valid = (
                new_state in (AppState.FAILED, AppState.STOPPING)
                or new_state in self._valid_transitions.get(old_state, [])
            )

            if not is_valid:
                logger.warning(
                    "Invalid state transition attempted: %s -> %s (Ignored)",
                    old_state.value,
                    new_state.value,
                )
                return False

            self._state = new_state

        logger.info(
            "State transition: %s -> %s %s",
            old_state.value,
            new_state.value,
            f"({reason})" if reason else "",
        )

        if self._event_bus:
            from backend.utils.event_bus import Event

            class StateChangedEvent(Event):
                def __init__(self, old_state: AppState, new_state: AppState, reason: str) -> None:
                    super().__init__(data={"old_state": old_state.value, "new_state": new_state.value, "reason": reason})
                    self.old_state = old_state
                    self.new_state = new_state
                    self.reason = reason

            self._event_bus.publish(
                StateChangedEvent(
                    old_state=old_state,
                    new_state=new_state,
                    reason=reason
                )
            )

        return True
