import os
import sys
import httpx

def get_api_key():
    try:
        # Look for .or file in the current working directory
        with open('.or', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print("Error: .or file containing API key not found.")
        sys.exit(1)

def list_models():
    api_key = get_api_key()
    url = "https://openrouter.ai/api/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/gemini-cli/bagh-chal", # Optional but good practice
        "X-Title": "Bagh-Chal CLI"
    }
    
    try:
        with httpx.Client() as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
        models = data.get("data", [])
        
        # Sort models alphabetically by ID
        models.sort(key=lambda x: x["id"])
        
        for model in models:
            model_id = model.get("id", "Unknown")
            pricing = model.get("pricing", {})
            
            # OpenRouter returns pricing as strings representing cost per token/image
            # We convert to float to check if it's 0
            try:
                prompt_cost = float(pricing.get("prompt", -1))
                completion_cost = float(pricing.get("completion", -1))
                image_cost = float(pricing.get("image", 0)) # Some models are image only
                request_cost = float(pricing.get("request", 0))
                
                # Consider it FREE only if all costs are 0
                if (prompt_cost == 0.0 and 
                    completion_cost == 0.0 and 
                    image_cost == 0.0 and 
                    request_cost == 0.0):
                    status = "FREE"
                else:
                    status = "PAID"
            except (ValueError, TypeError):
                # If pricing is malformed, assume PAID to be safe, or print Unknown
                status = "PAID"

            # Print format: Name + 4 spaces + Status
            print(f"{model_id}    {status}")
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    list_models()
