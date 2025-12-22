import argparse
import sys
import logging
import os
import json
import datetime

# Capture CWD before imports might change it (baghchal changes CWD on import)
ORIGINAL_CWD = os.getcwd()

from play import play_single_game, create_client, get_api_key, save_pgn, sanitize_filename

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def run_match_logic(model_a, model_b, experiment_name, bestof, client=None):
    if client is None:
        client = create_client(get_api_key())

    wins_a = 0
    wins_b = 0
    draws = 0
    games_needed = (bestof // 2) + 1
    
    durations = {model_a: [], model_b: []}
    
    # Helper to update durations
    def update_durations(new_durations):
        for m, times in new_durations.items():
            if m in durations:
                durations[m].extend(times)
            else:
                durations[m] = times # Should not happen if models consistent

    # Game 1: A is Goat
    logger.info(f"Match: {model_a} vs {model_b} | Game 1 (A=Goat)")
    winner, _, board, reason, game_durations = play_single_game(model_a, model_b, client)
    update_durations(game_durations)
    
    res_str = "*"
    if winner == 'G': 
        wins_a += 1
        res_str = "1-0"
    elif winner == 'B': 
        wins_b += 1
        res_str = "0-1"
    else: 
        draws += 1
        res_str = "1/2-1/2"
        
    save_pgn(board, experiment_name, bestof, model_a, model_b, res_str, reason)
    
    if wins_a < games_needed and wins_b < games_needed:
        # Game 2: B is Goat (Swap sides)
        logger.info(f"Match: {model_a} vs {model_b} | Game 2 (B=Goat)")
        winner, _, board, reason, game_durations = play_single_game(model_b, model_a, client)
        update_durations(game_durations)
        
        # model_b is White (Goat). Result "1-0" means B wins.
        res_str = "*"
        if winner == 'G': 
            wins_b += 1
            res_str = "1-0"
        elif winner == 'B': 
            wins_a += 1
            res_str = "0-1"
        else: 
            draws += 1
            res_str = "1/2-1/2"
            
        save_pgn(board, experiment_name, bestof, model_b, model_a, res_str, reason)

    # Further games
    game_idx = 3
    while (wins_a < games_needed and wins_b < games_needed) and game_idx <= bestof:
        # Alternate starter
        if game_idx % 2 != 0:
            p1, p2 = model_a, model_b
            logger.info(f"Match: {model_a} vs {model_b} | Game {game_idx} (A=Goat)")
        else:
            p1, p2 = model_b, model_a
            logger.info(f"Match: {model_a} vs {model_b} | Game {game_idx} (B=Goat)")
            
        winner, _, board, reason, game_durations = play_single_game(p1, p2, client)
        update_durations(game_durations)
        
        res_str = "*"
        
        if winner == 'G': # P1 wins
            res_str = "1-0"
            if p1 == model_a: wins_a += 1
            else: wins_b += 1
        elif winner == 'B': # P2 wins
            res_str = "0-1"
            if p1 == model_a: wins_b += 1
            else: wins_a += 1
        else:
            draws += 1
            res_str = "1/2-1/2"
            
        save_pgn(board, experiment_name, bestof, p1, p2, res_str, reason)
        game_idx += 1

    logger.info(f"Match Result: {model_a}: {wins_a}, {model_b}: {wins_b}, Draws: {draws}")
    
    score_a = 0.5
    if wins_a > wins_b: score_a = 1.0
    elif wins_b > wins_a: score_a = 0.0
    
    return score_a, durations

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a single Bagh-Chal match")
    parser.add_argument("experiment_name", help="Name of the experiment")
    parser.add_argument("bestof", type=int, help="Best of X games")
    parser.add_argument("model_a", help="Model A name")
    parser.add_argument("model_b", help="Model B name")
    
    args = parser.parse_args()
    
    score_a, durations = run_match_logic(args.model_a, args.model_b, args.experiment_name, args.bestof)
    
    # Save result to JSON
    sanitized_m1 = sanitize_filename(args.model_a)
    sanitized_m2 = sanitize_filename(args.model_b)
    filename = os.path.join(ORIGINAL_CWD, f"logs/match_results/{args.experiment_name}_{sanitized_m1}_vs_{sanitized_m2}.json")
    
    result_data = {
        "model_a": args.model_a,
        "model_b": args.model_b,
        "score_a": score_a,
        "durations": durations
    }
    
    with open(filename, "w") as f:
        json.dump(result_data, f)
        
    logger.info(f"Match result saved to {filename}")
