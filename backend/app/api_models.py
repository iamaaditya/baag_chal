from pydantic import BaseModel
from typing import List, Optional, Any

class GameConfig(BaseModel):
    mode: str = "PvC" # PvC (Player vs Computer), PvP, CvC
    difficulty: int = 3 # Depth for minimax

class MoveRequest(BaseModel):
    move: str # PGN string like "G11" or "G1213"

class GameState(BaseModel):
    board: List[List[Any]] # 5x5 grid
    turn: str
    goats_placed: int
    goats_captured: int
    baghs_trapped: int
    game_over: bool
    winner: Optional[str] = None
    fen: str
    pgn: str
    possible_moves: List[str]
    message: Optional[str] = None
