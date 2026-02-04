from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.main import app
from app.api.routes import verify_api_key
from app.api.schemas import ExtractedIntelligence
import time

# Override the API key dependency to bypass actual auth check
app.dependency_overrides[verify_api_key] = lambda: "test_key"

client = TestClient(app)

def test_flow():
    # Mock the graph.invoke method to return a standard result
    mock_intelligence = ExtractedIntelligence(
        bankAccounts=[],
        upiIds=[],
        phishingLinks=["http://scam.com"],
        phoneNumbers=[],
        suspiciousKeywords=["blocked"]
    )

    mock_result = {
        "scamDetected": True,
        "reply": "Why is my account blocked?",
        "intelligence": mock_intelligence,
        "agentNotes": "Detected scam link",
        "totalMessages": 1
    }

    # IMPORTANT: Start the patch where 'graph' is used/imported in the route handler
    with patch("app.api.routes.graph") as mock_graph:
        mock_graph.invoke.return_value = mock_result
        
        # 1. First Message
        response = client.post(
            "/process-message",
            headers={"x-api-key": "test_key"},
            json={
                "sessionId": "test-session",
                "message": {
                    "sender": "scammer",
                    "text": "Your account is blocked. Click http://scam.com",
                    "timestamp": int(time.time() * 1000)
                },
                "conversationHistory": [],
                "metadata": {"channel": "SMS", "language": "English", "locale": "IN"}
            }
        )
        
        print("\n--- Response 1 ---")
        print(f"Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error: {response.text}")
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["reply"] == "Why is my account blocked?"
        print("Test Passed Verification!")

if __name__ == "__main__":
    test_flow()
