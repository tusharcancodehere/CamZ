from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Type, Union

logger = logging.getLogger("camz.event_bus")


class Event:
    """Base class for all system events."""
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.timestamp = datetime.now(timezone.utc)
        self.data = data or {}

    @property
    def event_type(self) -> str:
        return self.__class__.__name__


class EventBus:
    """Thread-safe, in-memory Event Bus for decoupling services."""

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable[[Any], None]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: Union[Type[Event], str], callback: Callable[[Any], None]) -> None:
        """Subscribe a listener callback to an event type."""
        event_name = event_type if isinstance(event_type, str) else event_type.__name__
        with self._lock:
            if event_name not in self._listeners:
                self._listeners[event_name] = []
            if callback not in self._listeners[event_name]:
                self._listeners[event_name].append(callback)
        logger.debug("Subscribed listener %s to %s", callback.__name__, event_name)

    def unsubscribe(self, event_type: Union[Type[Event], str], callback: Callable[[Any], None]) -> None:
        """Unsubscribe a listener callback from an event type."""
        event_name = event_type if isinstance(event_type, str) else event_type.__name__
        with self._lock:
            if event_name in self._listeners and callback in self._listeners[event_name]:
                self._listeners[event_name].remove(callback)
        logger.debug("Unsubscribed listener %s from %s", callback.__name__, event_name)

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribed listeners."""
        event_name = event.event_type
        listeners_to_notify = []

        with self._lock:
            if event_name in self._listeners:
                listeners_to_notify.extend(self._listeners[event_name])
            if "*" in self._listeners:
                listeners_to_notify.extend(self._listeners["*"])

        if listeners_to_notify:
            logger.debug("Publishing %s to %d listeners", event_name, len(listeners_to_notify))
            for callback in listeners_to_notify:
                try:
                    callback(event)
                except Exception as exc:
                    logger.error("Error in listener %s processing event %s: %s", callback.__name__, event_name, exc)
