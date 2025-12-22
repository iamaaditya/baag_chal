import argparse
import sys
import logging
import os
import time

# Capture the original working directory before imports (baghchal changes CWD)
ORIGINAL_CWD = os.getcwd()

from openai import OpenAI
from baghchal.env import Board
from baghchal.lookup_table import reversed_action_space

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_api_key():
    try:
        file_path = os.path.join(ORIGINAL_CWD, '.or')
        with open(file_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.error(f"Error: .or file containing API key not found at {file_path}")
        sys.exit(1)

def create_client(api_key):
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

def get_valid_moves_str(board):
    moves = board.possible_moves()
    return ", ".join(sorted(list(moves)))

def format_board_for_llm(board):
    grid = [['.' for _ in range(5)] for _ in range(5)]
    for r in range(1, 6):
        for c in range(1, 6):
            piece = board[r, c]
            if piece:
                grid[r-1][c-1] = str(piece) # 'B' or 'G'
    
    board_str = "\n".join([" ".join(row) for row in grid])
    
    info = (
        f"Board State (5x5 Grid):\n{board_str}\n\n"
        f"Goats Placed: {board.goats_placed}/20\n"
        f"Goats Captured: {board.goats_captured}/5\n"
        f"Tigers Trapped: {board.baghs_trapped}/4\n"
        f"Current Turn: {'Goat (G)' if board.next_turn == 'G' else 'Tiger (B)'}\n"
    )
    return info

def get_llm_move(client, model, board, retries=3):
    valid_moves = get_valid_moves_str(board)
    board_info = format_board_for_llm(board)
    
    system_prompt = (
        "You are playing the board game Bagh-Chal (Tiger and Goat).\n"
        "You are an expert player.\n"
        "The board is a 5x5 grid. Coordinates are RowColumn (e.g., 11 is top-left, 55 is bottom-right).\n"
        "Goat (G) wins by trapping all 4 Tigers.\n"
        "Tiger (B) wins by capturing 5 Goats.\n"
        "Moves are in PGN format (e.g., 'G11' to place goat at 1,1; 'B1112' to move tiger from 1,1 to 1,2).\n"
        "Output ONLY the move string from the list of valid moves. Do not add explanation."
    )
    
    user_prompt = (
        f"{board_info}\n"
        f"Valid Moves: [{valid_moves}]\n"
        f"You are playing as {'Goat' if board.next_turn == 'G' else 'Tiger'}.\n"
        "Choose the best move from the list above. Return ONLY the move string."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2, 
            )
            
            content = response.choices[0].message.content.strip()
            # Clean up content more aggressively
            import re
            cleaned = re.sub(r'<[^>]+>', '', content) # remove html tags like <s>
            cleaned = re.sub(r'\[.*?\]', '', cleaned) # remove [OUT] etc
            cleaned = cleaned.replace('*', '').replace('`', '').strip()
            
            if cleaned:
                move = cleaned.split()[0].replace("'", "").replace('"', "").replace(".", "")
            else:
                move = ""
            
            possible = board.possible_moves()
            if move in possible:
                return move
            
            logger.info(f"Illegal move attempt {attempt+1}/{retries} by {model}: '{content}' (Parsed: '{move}'). Re-prompting with feedback...")
            
            # Append to history for feedback
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": f"Invalid move '{content}'. The valid moves are: [{valid_moves}]. Please output ONLY the move string from the list."})
            
        except Exception as e:
            logger.error(f"Error calling LLM {model}: {e}")
            # On API error, we might want to retry. The loop continues.
    
    return None

def play_single_game(model_goat, model_tiger, client=None):
    if client is None:
        client = create_client(get_api_key())
    
    board = Board()
    players = {'G': model_goat, 'B': model_tiger}
    # Store durations in seconds
    move_durations = {model_goat: [], model_tiger: []}
    
    logger.info(f"Starting Game: {model_goat} (Goat) vs {model_tiger} (Tiger)")
    
    max_moves = 200
    move_count = 0
    winner_code = None
    termination_reason = "Normal"
    
    while not board.is_game_over() and move_count < max_moves:
        time.sleep(2) # Rate limit friendly delay
        
        current_turn = board.next_turn
        current_model = players[current_turn]
        
        start_time = time.time()
        move = get_llm_move(client, current_model, board)
        end_time = time.time()
        duration = end_time - start_time
        move_durations[current_model].append(duration)
        
        if not move:
            logger.info(f"Game aborted. {current_model} ({current_turn}) failed to generate a valid move.")
            # Forfeit: Opponent wins
            winner_code = 'B' if current_turn == 'G' else 'G'
            termination_reason = "Illegal Move"
            board.pgn += f" {{Forfeit: {current_model} made illegal move}}"
            break
            
        logger.info(f"Turn {move_count+1}: {current_turn} ({current_model}) plays {move} ({duration:.2f}s)")
        
        try:
            board.move(move)
            move_count += 1
            if logger.level == logging.DEBUG:
                logger.debug(f"FEN: {board.fen}")
        except Exception as e:
            logger.error(f"Fatal error executing move {move}: {e}")
            winner_code = 'B' if current_turn == 'G' else 'G'
            termination_reason = "Error"
            break
            
    if board.is_game_over() and termination_reason == "Normal":
        winner_code = board.winner()
    
    return winner_code, move_count, board, termination_reason, move_durations

def play_game(model1, model2):
    winner_code, move_count, board, reason, durations = play_single_game(model1, model2)
    
    if winner_code == 'G':
        winner = f"Goat ({model1})"
    elif winner_code == 'B':
        winner = f"Tiger ({model2})"
    elif winner_code == 'Draw' or winner_code == 0: 
        winner = "Draw"
    else:
        winner = "Aborted/Unknown"

    logger.info(f"Game Over! Winner: {winner}")
    logger.info(f"Total Moves: {move_count}")
    logger.info(f"Final FEN: {board.fen}")
    logger.info(f"PGN: {board.pgn}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play Bagh-Chal with LLMs")
    parser.add_argument("model1", help="Model name for Player 1 (Goat)")
    parser.add_argument("model2", help="Model name for Player 2 (Tiger)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
        
    play_game(args.model1, args.model2)
