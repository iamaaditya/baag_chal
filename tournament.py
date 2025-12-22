import argparse
import sys
import logging
import os
import datetime
import re
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from itertools import combinations

# Capture CWD before imports might change it
ORIGINAL_CWD = os.getcwd()

from play import play_single_game, create_client, get_api_key

# Configure logging
# Logging configuration will be set up in run_tournament to direct output to file
logger = logging.getLogger(__name__)

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9]', '', name)

def save_pgn(board, experiment_name, bestof, model1, model2, result, termination_reason):
    timestamp = datetime.datetime.now().strftime("%Y_%m_%d")
    sanitized_m1 = sanitize_filename(model1)
    sanitized_m2 = sanitize_filename(model2)
    filename = os.path.join(ORIGINAL_CWD, f"logs/game_logs/{timestamp}_{experiment_name}_bestof{bestof}_{sanitized_m1}_vs_{sanitized_m2}.pgn")
    
    # Construct PGN header
    date_str = datetime.datetime.now().strftime("%Y.%m.%d")
    pgn_content = f"""
[Event "{experiment_name}"]
[Site "Bagh-Chal CLI Tournament"]
[Date "{date_str}"]
[Round "BestOf{bestof}"]
[White "{model1} (Goat)"]
[Black "{model2} (Tiger)"]
[Result "{result}"]
[Termination "{termination_reason}"]

{board.pgn}
"""
    
    with open(filename, "a") as f:
        f.write(pgn_content + "\n\n")

def run_match(model_a, model_b, client, experiment_name, bestof, all_durations):
    """
    Runs a best of `bestof` match between model_a and model_b.
    Returns score for model_a (1.0 win, 0.0 loss, 0.5 draw)
    Also updates all_durations dict with timing info.
    """
    wins_a = 0
    wins_b = 0
    draws = 0
    games_needed = (bestof // 2) + 1
    
    # Game 1: A is Goat
    logger.info(f"Match: {model_a} vs {model_b} | Game 1 (A=Goat)")
    winner, _, board, reason, durations = play_single_game(model_a, model_b, client)
    
    # Update global durations
    for m, times in durations.items():
        all_durations[m].extend(times)
    
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
    
    if wins_a >= games_needed: return 1.0
    if wins_b >= games_needed: return 0.0
    
    # Game 2: B is Goat (Swap sides)
    logger.info(f"Match: {model_a} vs {model_b} | Game 2 (B=Goat)")
    winner, _, board, reason, durations = play_single_game(model_b, model_a, client)
    
    for m, times in durations.items():
        all_durations[m].extend(times)
        
    # model_b is White (Goat). Result "1-0" means B wins.
    res_str = "*"
    if winner == 'G': 
        wins_b += 1
        res_str = "1-0" # White (B) wins
    elif winner == 'B': 
        wins_a += 1
        res_str = "0-1" # Black (A) wins
    else:
        draws += 1
        res_str = "1/2-1/2"
        
    save_pgn(board, experiment_name, bestof, model_b, model_a, res_str, reason)

    if wins_a >= games_needed: return 1.0
    if wins_b >= games_needed: return 0.0
    
    # Further games if needed and bestof > 2
    game_idx = 3
    while game_idx <= bestof:
        if wins_a >= games_needed or wins_b >= games_needed:
            break
            
        # Alternate starter
        if game_idx % 2 != 0:
            p1, p2 = model_a, model_b
            logger.info(f"Match: {model_a} vs {model_b} | Game {game_idx} (A=Goat)")
        else:
            p1, p2 = model_b, model_a
            logger.info(f"Match: {model_a} vs {model_b} | Game {game_idx} (B=Goat)")
            
        winner, _, board, reason, durations = play_single_game(p1, p2, client)
        
        for m, times in durations.items():
            all_durations[m].extend(times)
            
        res_str = "*"
        current_a_win = False
        current_b_win = False
        
        if winner == 'G': # P1 wins
            res_str = "1-0"
            if p1 == model_a: wins_a += 1; current_a_win=True
            else: wins_b += 1; current_b_win=True
        elif winner == 'B': # P2 wins
            res_str = "0-1"
            if p1 == model_a: wins_b += 1; current_b_win=True
            else: wins_a += 1; current_a_win=True
        else:
            draws += 1
            res_str = "1/2-1/2"
            
        save_pgn(board, experiment_name, bestof, p1, p2, res_str, reason)
        game_idx += 1

    logger.info(f"Match Result: {model_a}: {wins_a}, {model_b}: {wins_b}, Draws: {draws}")
    
    if wins_a > wins_b: return 1.0
    if wins_b > wins_a: return 0.0
    return 0.5

def setup_logging(experiment_name, bestof):
    timestamp = datetime.datetime.now().strftime("%Y_%m_%d")
    log_filename = os.path.join(ORIGINAL_CWD, f"logs/tournament_logs/{timestamp}_{experiment_name}_bestof{bestof}.log")
    
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # Add to root logger
    root = logging.getLogger()
    # Clear existing handlers to prevent double logging if setup called multiple times
    if root.handlers:
        root.handlers = []
        
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    
    # Also log to stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)
    
    logger.info(f"Logging tournament to {log_filename}")

def run_tournament(experiment_name, bestof, models):
    setup_logging(experiment_name, bestof)
    client = create_client(get_api_key())
    
    scores = pd.DataFrame(0.0, index=models, columns=models)
    all_durations = {m: [] for m in models}
    
    for model_a, model_b in combinations(models, 2):
        logger.info(f"--- Starting Match: {model_a} vs {model_b} ---")
        result_a = run_match(model_a, model_b, client, experiment_name, bestof, all_durations)
        
        scores.loc[model_a, model_b] = result_a
        scores.loc[model_b, model_a] = 1.0 - result_a if result_a != 0.5 else 0.5
    
    logger.info("\nTournament Results (Score Matrix):")
    logger.info("\n" + str(scores))
    
    logger.info("\nTiming Statistics (Seconds per move):")
    for model in models:
        times = all_durations[model]
        if times:
            mean_t = np.mean(times)
            median_t = np.median(times)
            std_t = np.std(times)
            logger.info(f"{model}: Mean={mean_t:.2f}s, Median={median_t:.2f}s, StdDev={std_t:.2f}s (N={len(times)})")
        else:
            logger.info(f"{model}: No moves played.")
    
    # Save confusion matrix
    try:
        plt.figure(figsize=(10, 8))
        sns.heatmap(scores, annot=True, cmap='coolwarm', vmin=0, vmax=1)
        plt.title(f'Tournament: {experiment_name} (BestOf{bestof})')
        plt.tight_layout()
        plot_filename = os.path.join(ORIGINAL_CWD, f"logs/tournament_logs/{datetime.datetime.now().strftime('%Y_%m_%d')}_{experiment_name}_results.png")
        plt.savefig(plot_filename)
        logger.info(f"Saved results plot to {plot_filename}")
    except Exception as e:
        logger.error(f"Failed to save plot: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a Bagh-Chal LLM Tournament")
    parser.add_argument("experiment_name", help="Name of the experiment")
    parser.add_argument("bestof", nargs='?', type=int, default=3, help="Best of X games per match")
    parser.add_argument("--models", nargs='+', required=True, help="List of model names")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    run_tournament(args.experiment_name, args.bestof, args.models)