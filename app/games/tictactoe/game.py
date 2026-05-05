class TicTacToeGame:
    code = "tic_tac_toe"
    title = "Tic-Tac-Toe"

    def new_game_state(self) -> dict:
        return {
            "board_size": 3,
            "board": ["", "", "", "", "", "", "", "", ""],
            "current_symbol": "X",
            "status": "active",
        }

    def supports_mode(self, mode: str) -> bool:
        return mode in {"solo", "duel_private", "group_match"}

