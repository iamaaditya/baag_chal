from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uuid
from typing import Dict
import os

from baghchal.env import Board
from baghchal.engine import Engine
from .api_models import GameConfig, MoveRequest, GameState

app = FastAPI(title="Bagh Chal API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store
games: Dict[str, Dict] = {}

def get_game_state(game_id: str, board: Board, message: str = None) -> GameState:
    winner = None
    if board.is_game_over():
        try:
            winner = str(board.winner())
        except:
            winner = "Draw"
            
    # Serialize board for frontend
    # Board object is not directly serializable, need to convert to list of lists of strings/ints
    board_data = [[str(c) if c != 0 else "" for c in row] for row in board.board]
    
    return GameState(
        board=board_data,
        turn=board.next_turn,
        goats_placed=board.goats_placed,
        goats_captured=board.goats_captured,
        baghs_trapped=board.baghs_trapped,
        game_over=board.is_game_over(),
        winner=winner,
        fen=board.fen,
        pgn=board.pgn,
        possible_moves=list(board.possible_moves()) if not board.is_game_over() else [],
        message=message
    )

@app.post("/api/games", response_model=Dict[str, str])
async def create_game(config: GameConfig):
    game_id = str(uuid.uuid4())
    board = Board()
    engine = Engine(depth=config.difficulty)
    games[game_id] = {
        "board": board,
        "engine": engine,
        "config": config
    }
    return {"game_id": game_id}

@app.get("/api/games/{game_id}", response_model=GameState)
async def get_game(game_id: str):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = games[game_id]
    return get_game_state(game_id, game["board"])

@app.post("/api/games/{game_id}/move", response_model=GameState)
async def make_move(game_id: str, move_req: MoveRequest):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = games[game_id]
    board = game["board"]
    
    try:
        # Use pure_move to handle simplified coordinates (e.g. "11", "1112")
        # and automatically detect captures vs moves.
        board.pure_move(move_req.move)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return get_game_state(game_id, board, message="Move accepted")

@app.post("/api/games/{game_id}/bot-move", response_model=GameState)
async def bot_move(game_id: str):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = games[game_id]
    board = game["board"]
    engine = game["engine"]
    
    if board.is_game_over():
        return get_game_state(game_id, board, message="Game over")
        
    try:
        best_move, _ = engine.get_best_move(board)
        # best_move returned by engine is a string like "1112" or "11" (no prefix?)
        # Let's verify what get_best_move returns.
        # Checking engine.py: it returns `best_move` which comes from `board.possible_moves()`.
        # `possible_moves` returns sets of strings like "G11" or "B1122".
        # So it should be directly usable in `board.move()`.
        
        if best_move:
             board.move(best_move)
             msg = f"Bot played {best_move}"
        else:
             msg = "Bot has no moves (Game Over?)"
             
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bot failed: {str(e)}")

    return get_game_state(game_id, board, message=msg)

# Serve Frontend
frontend_path = os.path.join(os.path.dirname(__file__), "../../frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
