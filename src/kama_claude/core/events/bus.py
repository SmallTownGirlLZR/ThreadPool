from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

type EventHandler = Callable[[BaseModel], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[EventHandler] = []

    # EventWriter -> write events to event.jsonl 
    # _trace_event_handler , IpcEventBroadcaster.handle, 
    def subscribe(self, handler: EventHandler) -> None:
        self._subscribers.append(handler)

    # 按注册顺序依次调用所有订阅者
    async def publish(self, event: BaseModel) -> None:
        for handler in self._subscribers:
            await handler(event)
