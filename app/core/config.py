import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Agentic Honey-Pot API"
    API_V1_STR: str = "/api/v1"
    
    #Auth
    YOUR_SECRET_API_KEY: str = (os.getenv("YOUR_SECRET_API_KEY") or "default_secret_key").strip().strip('"').strip("'")
    
    # Groq API key
    GROQ_API_KEY: str = (os.getenv("GROQ_API_KEY") or "").strip().strip('"').strip("'")
    
    # Hackathon endpoint
    CALLBACK_URL: str = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"

settings = Settings()
