import argparse
import sys
import httpx
import pandas as pd
import logging
from list_models import get_api_key

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_all_models_pricing(api_key):
    url = "https://openrouter.ai/api/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/gemini-cli/bagh-chal",
        "X-Title": "Bagh-Chal CLI"
    }
    
    try:
        with httpx.Client() as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
    except Exception as e:
        logger.error(f"Failed to fetch models: {e}")
        sys.exit(1)

def show_prices(requested_models):
    api_key = get_api_key()
    all_models = get_all_models_pricing(api_key)
    
    # Create a lookup dict
    model_map = {m["id"]: m for m in all_models}
    
    rows = []
    
    for model_name in requested_models:
        if model_name in model_map:
            data = model_map[model_name]
            pricing = data.get("pricing", {})
            rows.append({
                "Model": model_name,
                "Prompt ($/1M)": float(pricing.get("prompt", 0)) * 1_000_000,
                "Completion ($/1M)": float(pricing.get("completion", 0)) * 1_000_000,
                "Image ($)": float(pricing.get("image", 0)),
                "Request ($)": float(pricing.get("request", 0))
            })
        else:
            rows.append({
                "Model": model_name,
                "Prompt ($/1M)": "N/A",
                "Completion ($/1M)": "N/A",
                "Image ($)": "N/A",
                "Request ($)": "N/A"
            })
            
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get pricing for OpenRouter models")
    parser.add_argument("models", nargs='+', help="List of model names")
    
    args = parser.parse_args()
    show_prices(args.models)
