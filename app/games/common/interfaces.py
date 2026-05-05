from typing import Protocol


class GameModule(Protocol):
    code: str
    title: str

    def new_game_state(self) -> dict: ...
    def supports_mode(self, mode: str) -> bool: ...

