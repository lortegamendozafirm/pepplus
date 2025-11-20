from dataclasses import dataclass
from typing import Iterable, List

from domain.slot import Slot


@dataclass
class Manifest:
    slots: List[Slot]

    def __post_init__(self) -> None:
        slots_by_position = {}
        for slot in self.slots:
            if slot.slot in slots_by_position:
                raise ValueError(f"Duplicated slot position detected: {slot.slot}")
            slots_by_position[slot.slot] = slot
        self.slots = sorted(self.slots, key=lambda s: s.slot)

    def presence_mask(self, resolved_slots: Iterable[int]) -> str:
        present = set(resolved_slots)
        return "".join("1" if slot.slot in present else "0" for slot in self.slots)

    def required_missing(self, resolved_slots: Iterable[int]) -> list[int]:
        present = set(resolved_slots)
        return [slot.slot for slot in self.slots if slot.required and slot.slot not in present]
