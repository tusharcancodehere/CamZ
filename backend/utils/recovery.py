from __future__ import annotations

import logging
import time
from typing import Callable

from backend.utils.event_bus import Event, EventBus
from backend.utils.state_machine import ApplicationStateMachine, AppState

logger = logging.getLogger("camz.recovery")


class RecoveryStarted(Event):
    def __init__(self, stage: int, component: str) -> None:
        super().__init__(data={"stage": stage, "component": component})
        self.stage = stage
        self.component = component


class RecoverySucceeded(Event):
    def __init__(self, stage: int, component: str) -> None:
        super().__init__(data={"stage": stage, "component": component})
        self.stage = stage
        self.component = component


class RecoveryFailed(Event):
    def __init__(self, stage: int, component: str, error: str) -> None:
        super().__init__(data={"stage": stage, "component": component, "error": error})
        self.stage = stage
        self.component = component
        self.error = error


class ProgressiveRecoveryEngine:
    """Progressive recovery manager for self-healing application components."""

    def __init__(
        self,
        event_bus: EventBus,
        state_machine: ApplicationStateMachine,
        max_retries: int = 3,
        cooldown_seconds: float = 2.0,
    ) -> None:
        self._event_bus = event_bus
        self._state_machine = state_machine
        self._max_retries = max_retries
        self._cooldown_seconds = cooldown_seconds
        self._last_recovery_time = 0.0
        self._retry_count = 0
        self._current_stage = 1

    def handle_failure(self, component: str, failure_trigger: Callable[[], bool]) -> bool:
        """Attempt progressive recovery for a failed component.

        Returns True if recovery succeeded, False otherwise.
        """
        now = time.monotonic()
        if now - self._last_recovery_time < self._cooldown_seconds:
            logger.warning("Recovery loop triggered too quickly, enforcing cooldown...")
            return False

        self._last_recovery_time = now

        if self._retry_count >= self._max_retries:
            logger.error("Maximum recovery retries (%d) exhausted for component %s.", self._max_retries, component)
            self._state_machine.transition_to(AppState.FAILED, f"Recovery retries exhausted for {component}")
            return False

        self._state_machine.transition_to(AppState.RECOVERING, f"Recovering component {component}")
        logger.info("Executing recovery stage %d for component: %s", self._current_stage, component)

        self._event_bus.publish(RecoveryStarted(stage=self._current_stage, component=component))

        success = False
        try:
            success = failure_trigger()
        except Exception as exc:
            logger.error("Exception occurred during recovery stage %d: %s", self._current_stage, exc)
            self._event_bus.publish(RecoveryFailed(stage=self._current_stage, component=component, error=str(exc)))

        if success:
            logger.info("Recovery stage %d succeeded for component %s.", self._current_stage, component)
            self._event_bus.publish(RecoverySucceeded(stage=self._current_stage, component=component))

            self._retry_count = 0
            self._current_stage = 1

            self._state_machine.transition_to(AppState.READY, f"Recovery succeeded for {component}")
            return True

        logger.warning("Recovery stage %d failed for component %s.", self._current_stage, component)
        self._event_bus.publish(RecoveryFailed(stage=self._current_stage, component=component, error="Trigger returned false"))

        self._retry_count += 1
        if self._current_stage < 4:
            self._current_stage += 1
        else:
            self._current_stage = 1

        return False
