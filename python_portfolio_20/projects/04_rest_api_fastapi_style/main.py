from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Item:
    id: int
    name: str


class ItemService:
    def __init__(self) -> None:
        self._items: dict[int, Item] = {}
        self._next_id = 1

    def create(self, name: str) -> Item:
        if not name.strip():
            raise ValueError('name must not be empty')
        item = Item(id=self._next_id, name=name)
        self._items[item.id] = item
        self._next_id += 1
        return item

    def list_all(self) -> list[Item]:
        return list(self._items.values())


def run_demo() -> dict[str, object]:
    svc = ItemService()
    svc.create('first-task')
    svc.create('second-task')
    return {'project': 'rest_api_fastapi_style', 'count': len(svc.list_all())}


if __name__ == '__main__':
    print(run_demo())
