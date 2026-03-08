from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Page:
    index: int
    allocated: bool = False
    owner: str = ""


class PageAllocator:
    def __init__(self, page_count: int = 256) -> None:
        self.pages = [Page(i) for i in range(max(1, int(page_count)))]

    def alloc(self, owner: str) -> int | None:
        for page in self.pages:
            if not page.allocated:
                page.allocated = True
                page.owner = owner
                return page.index
        return None

    def free(self, index: int) -> bool:
        if index < 0 or index >= len(self.pages):
            return False
        page = self.pages[index]
        if not page.allocated:
            return False
        page.allocated = False
        page.owner = ""
        return True

    def stats(self) -> dict:
        used = sum(1 for p in self.pages if p.allocated)
        total = len(self.pages)
        return {"total_pages": total, "used_pages": used, "free_pages": total - used}
