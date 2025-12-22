import os
import glob
import re
import math
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

ELO_DIR = "logs/elos"
GAME_LOGS_DIR = "logs/game_logs"
DEFAULT_ELO = 1200
K_FACTOR = 32

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9]', '', name)

def get_expected_score(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

def update_ratings(rating_a, rating_b, score_a):
    expected_a = get_expected_score(rating_a, rating_b)
    new_rating_a = rating_a + K_FACTOR * (score_a - expected_a)
    new_rating_b = rating_b + K_FACTOR * ((1 - score_a) - (1 - expected_a))
    return new_rating_a, new_rating_b

def parse_pgn(filepath):
    """
    Parses a PGN file to extract White, Black, and Result.
    """
    white = None
    black = None
    result = None
    
    with open(filepath, 'r') as f:
        content = f.read()
        
    # Extract headers using regex
    white_match = re.search(r'[\[]White "(.*?)( \(Goat\))?"[\]]', content)
    black_match = re.search(r'[\[]Black "(.*?)( \(Tiger\))?"[\]]', content)
    result_match = re.search(r'[\[]Result "(.*?)"[\]]', content)
    
    if white_match:
        white = white_match.group(1) # Group 1 is model name, Group 2 is " (Goat)"
    if black_match:
        black = black_match.group(1)
    if result_match:
        result = result_match.group(1)
        
    return white, black, result

def result_to_score(result):
    if result == "1-0": return 1.0
    if result == "0-1": return 0.0
    if result == "1/2-1/2": return 0.5
    return None # Invalid or unknown

def calculate_elos():
    # 1. Gather all game logs
    pgn_files = glob.glob(os.path.join(GAME_LOGS_DIR, "*.pgn"))
    
    # 2. Sort by timestamp in filename to process chronologically
    # Filename format: YYYY_MM_DD_experiment_bestofX_m1_vs_m2.pgn
    # We rely on the YYYY_MM_DD at start, but that might not be granular enough if many games in one day.
    # However, glob ordering isn't guaranteed.
    # Let's try to parse the timestamp from the filename if possible, or just sort strings.
    # String sort works for YYYY_MM_DD...
    pgn_files.sort()
    
    ratings = {}
    
    logger.info(f"Found {len(pgn_files)} game logs. Calculating ELOs...")
    
    for filepath in pgn_files:
        white, black, result = parse_pgn(filepath)
        
        if not white or not black or not result:
            logger.warning(f"Skipping malformed PGN: {filepath}")
            continue
            
        score_white = result_to_score(result)
        if score_white is None:
            logger.warning(f"Skipping game with unknown result '{result}': {filepath}")
            continue
            
        # Initialize ratings if new
        if white not in ratings: ratings[white] = DEFAULT_ELO
        if black not in ratings: ratings[black] = DEFAULT_ELO
        
        old_white = ratings[white]
        old_black = ratings[black]
        
        # Update
        new_white, new_black = update_ratings(old_white, old_black, score_white)
        
        ratings[white] = new_white
        ratings[black] = new_black
        
        logger.debug(f"Game: {white} ({old_white:.1f}) vs {black} ({old_black:.1f}) | Result: {result} -> New: {new_white:.1f}, {new_black:.1f}")

    # 3. Write to files
    logger.info("Updating ELO files in logs/elos/...")
    for model, rating in ratings.items():
        sanitized = sanitize_filename(model)
        filepath = os.path.join(ELO_DIR, f"{sanitized}.txt")
        try:
            with open(filepath, 'w') as f:
                f.write(f"{rating:.2f}")
            logger.info(f"Saved {model}: {rating:.2f} to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save ELO for {model}: {e}")

    # Also save a summary CSV
    summary_path = os.path.join(ELO_DIR, "summary.csv")
    with open(summary_path, 'w') as f:
        f.write("Model,ELO\n")
        # Sort by rating descending
        sorted_models = sorted(ratings.items(), key=lambda x: x[1], reverse=True)
        for m, r in sorted_models:
            f.write(f"{m},{r:.2f}\n")
    logger.info(f"Saved summary to {summary_path}")

if __name__ == "__main__":
    calculate_elos()
