import argparse
import sys
import logging
import os
import datetime
import re
import glob
import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from itertools import combinations

# Capture CWD before imports might change it
ORIGINAL_CWD = os.getcwd()

# play.py imports baghchal, which changes CWD.
# But we only need create_client/get_api_key if we run tournament directly.
# sanitize_filename is in play.py now.
# We will import run_match_logic from run_match.py instead of defining it here.
# But run_match.py is a script. We should import `run_match_logic` from it if we can.
# Or just copy the logic. `run_match.py` imports `play.py`.
# Let's import `run_match_logic` from `run_match` module.
# To do that, `run_match.py` needs to be importable.
# It is in the same directory.
from run_match import run_match_logic
from play import create_client, get_api_key, sanitize_filename

# Configure logging
logger = logging.getLogger(__name__)

def setup_logging(experiment_name, bestof):
    timestamp = datetime.datetime.now().strftime("%Y_%m_%d")
    log_filename = os.path.join(ORIGINAL_CWD, f"logs/tournament_logs/{timestamp}_{experiment_name}_bestof{bestof}.log")
    
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    root = logging.getLogger()
    if root.handlers:
        root.handlers = []
        
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)
    
    logger.info(f"Logging tournament to {log_filename}")

def generate_commands(experiment_name, bestof, models, output_file):
    # Ensure output file is in ORIGINAL_CWD if it's a relative path
    if not os.path.isabs(output_file):
        output_file = os.path.join(ORIGINAL_CWD, output_file)
        
    with open(output_file, 'w') as f:
        for model_a, model_b in combinations(models, 2):
            cmd = f"python run_match.py {experiment_name} {bestof} \"{model_a}\" \"{model_b}\""
            f.write(cmd + "\n")
    print(f"Generated {len(list(combinations(models, 2)))} commands in {output_file}")

def analyze_results(experiment_name, bestof, models):
    setup_logging(experiment_name, bestof)
    logger.info(f"Analyzing results for experiment: {experiment_name}")
    
    scores = pd.DataFrame(0.0, index=models, columns=models)
    all_durations = {m: [] for m in models}
    
    # Read all JSON files matching experiment name
    # Pattern: logs/match_results/{experiment_name}_*.json
    # Note: filenames might have sanitized model names.
    # It's safer to read ALL jsons and filter by checking content if we can,
    # or trust the filename start.
    pattern = os.path.join(ORIGINAL_CWD, "logs/match_results", f"{experiment_name}_*.json")
    files = glob.glob(pattern)
    
    logger.info(f"Found {len(files)} result files.")
    
    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                
            model_a = data.get("model_a")
            model_b = data.get("model_b")
            score_a = data.get("score_a")
            durations = data.get("durations", {})
            
            # Check if these models are in our current list (tournament subset)
            if model_a in models and model_b in models:
                scores.loc[model_a, model_b] = score_a
                scores.loc[model_b, model_a] = 1.0 - score_a if score_a != 0.5 else 0.5
                
                for m, times in durations.items():
                    if m in all_durations:
                        all_durations[m].extend(times)
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")

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
            logger.info(f"{model}: No moves played (or data missing).")
            
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

def run_serial_tournament(experiment_name, bestof, models):
    setup_logging(experiment_name, bestof)
    client = create_client(get_api_key())
    
    scores = pd.DataFrame(0.0, index=models, columns=models)
    all_durations = {m: [] for m in models}
    
    for model_a, model_b in combinations(models, 2):
        logger.info(f"--- Starting Match: {model_a} vs {model_b} ---")
        
        # We reuse logic from run_match.py but we need it to return score and durations
        # run_match_logic(model_a, model_b, experiment_name, bestof, client) -> (score_a, durations)
        score_a, durations = run_match_logic(model_a, model_b, experiment_name, bestof, client)
        
        scores.loc[model_a, model_b] = score_a
        scores.loc[model_b, model_a] = 1.0 - score_a if score_a != 0.5 else 0.5
        
        for m, times in durations.items():
            all_durations[m].extend(times)
            
        # Also save the result JSON for consistency?
        sanitized_m1 = sanitize_filename(model_a)
        sanitized_m2 = sanitize_filename(model_b)
        filename = os.path.join(ORIGINAL_CWD, f"logs/match_results/{experiment_name}_{sanitized_m1}_vs_{sanitized_m2}.json")
        try:
            with open(filename, "w") as f:
                json.dump({
                    "model_a": model_a,
                    "model_b": model_b,
                    "score_a": score_a,
                    "durations": durations
                }, f)
        except Exception as e:
            logger.error(f"Failed to save JSON result: {e}")
    
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
    parser.add_argument("--generate-commands", metavar="FILE", help="Generate command list to FILE instead of running")
    parser.add_argument("--analyze", action="store_true", help="Analyze existing results in logs/match_results instead of running")
    
    args = parser.parse_args()
    
    if args.generate_commands:
        generate_commands(args.experiment_name, args.bestof, args.models, args.generate_commands)
    elif args.analyze:
        analyze_results(args.experiment_name, args.bestof, args.models)
    else:
        run_serial_tournament(args.experiment_name, args.bestof, args.models)
