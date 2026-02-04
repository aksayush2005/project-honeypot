import os
import requests
from fastapi import APIRouter, Header, HTTPException, Depends, BackgroundTasks
from app.api.schemas import ScamRequest, ScamResponse, FinalResultPayload
from app.core.graph import create_graph, init_state
from app.core.config import settings

router = APIRouter()

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.YOUR_SECRET_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return x_api_key

graph = create_graph()

def send_final_report(payload: FinalResultPayload):
    try:
        # Use direct dict conversion for compatibility with requests
        data = payload.dict()
        response = requests.post(settings.CALLBACK_URL, json=data, timeout=10)
        print(f"Callback status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Failed to send callback for session {payload.sessionId}: {e}")

@router.post("/process-message", response_model=ScamResponse)
async def process_message(
    request: ScamRequest, 
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    try:
        # Initialize state from request
        metadata_dict = request.metadata.dict() if request.metadata else None
        state = init_state(request.sessionId, request.conversationHistory, request.message, metadata_dict)
        
        # Run graph
        result = graph.invoke(state)
        
        # Determine if we should send a report
        if result.get("scamDetected"):
            intelligence = result.get("intelligence")
            # Heuristic: Send if we found specific intel OR after 3 total messages
            has_intel = any([
                intelligence.upiIds, 
                intelligence.bankAccounts, 
                intelligence.phishingLinks, 
                intelligence.phoneNumbers
            ])
            
            if has_intel or result.get("totalMessages", 0) >= 3:
                payload = FinalResultPayload(
                    sessionId=request.sessionId,
                    scamDetected=True,
                    totalMessagesExchanged=result.get("totalMessages", 0),
                    extractedIntelligence=intelligence,
                    agentNotes=result.get("agentNotes", "Scam detected and intelligence gathering in progress.")
                )
                background_tasks.add_task(send_final_report, payload)

            return ScamResponse(status="success", reply=result.get("reply", "I'm interested, tell me more."))
        
        else:
            # If not detected as scam (yet)
            return ScamResponse(status="success", reply="Thank you for the information. I'll get back to you.")

    except Exception as e:
        print(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
