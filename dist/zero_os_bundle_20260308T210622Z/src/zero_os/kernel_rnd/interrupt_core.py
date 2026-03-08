from __future__ import annotations


class InterruptController:
    def __init__(self) -> None:
        self.handlers: dict[int, str] = {}

    def register(self, irq: int, handler_name: str) -> dict:
        self.handlers[int(irq)] = handler_name
        return {"ok": True, "irq": int(irq), "handler": handler_name}

    def dispatch(self, irq: int) -> dict:
        h = self.handlers.get(int(irq))
        return {"ok": h is not None, "irq": int(irq), "handler": h}
