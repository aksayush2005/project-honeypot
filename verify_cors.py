import requests
import sys

def verify_api():
    url = "http://localhost:8000/process-message"
    
    # 1. Test CORS preflight (OPTIONS)
    print("Testing CORS Preflight...")
    try:
        # CORS middleware requires Origin header to respond
        headers = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
        response = requests.options(url, headers=headers)
        print(f"OPTIONS Status: {response.status_code}")
        
        allow_origin = response.headers.get("access-control-allow-origin")
        print(f"Access-Control-Allow-Origin: {allow_origin}")
        
        # When allow_credentials=True, FastAPI returns the specific origin, not "*"
        if allow_origin == "*" or allow_origin == headers["Origin"]:
            print("SUCCESS: CORS allowed.")
        else:
            print(f"FAILURE: CORS not configured correctly. Got: {allow_origin}")
            # sys.exit(1) # Don't exit yet, try POST
            
    except Exception as e:
        print(f"Failed to connect for OPTIONS: {e}")
        sys.exit(1)

    # 2. Test Minimal POST Request
    print("\nTesting POST Request...")
    payload = {
        "sessionId": "verify-script",
        "message": {
            "sender": "verifier",
            "text": "ping",
            "timestamp": 1234567890
        },
        "conversationHistory": []
    }
    headers = {
        "x-api-key": "default_secret_key" # Using default as per config.py if env not set
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"POST Status: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("SUCCESS: API call worked.")
        else:
            print(f"WARNING: API call returned {response.status_code}")

    except Exception as e:
        print(f"Failed to connect for POST: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_api()
