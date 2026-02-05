import os
from typing import Annotated, List, Union, Dict
from typing_extensions import TypedDict

from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from app.api.schemas import ExtractedIntelligence, Message as ApiMessage
from app.core.config import settings

class AgentState(TypedDict):
    messages: List[BaseMessage]
    sessionId: str
    scamDetected: bool
    intelligence: ExtractedIntelligence
    agentNotes: str
    reply: str
    totalMessages: int
    metadata: Dict[str, str]

def init_state(session_id: str, history: List[ApiMessage], current_message: ApiMessage, metadata: Dict[str, str] = None) -> AgentState:
    messages = []
    # Add a system message to set the stage if it's the beginning
    if not history:
        messages.append(SystemMessage(content="New conversation started."))
        
    for msg in history:
        if msg.sender == "scammer":
            messages.append(HumanMessage(content=msg.text))
        else:
            messages.append(AIMessage(content=msg.text))
    
    messages.append(HumanMessage(content=current_message.text))
    
    return {
        "messages": messages,
        "sessionId": session_id,
        "scamDetected": False,
        "intelligence": ExtractedIntelligence(),
        "agentNotes": "",
        "reply": "",
        "totalMessages": len(history) + 1,
        "metadata": metadata or {"channel": "SMS", "language": "English", "locale": "IN"}
    }

def analyze_intent(state: AgentState):
    # Use a faster model for intent analysis to avoid Vercel timeouts
    llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0, api_key=settings.GROQ_API_KEY)
    
    # Analyze the whole conversation context
    conversation_text = "\n".join([f"{msg.type}: {msg.content}" for msg in state["messages"] if not isinstance(msg, SystemMessage)])
    
    prompt = f"""
    Analyze the following conversation for scam intent (phishing, bank fraud, UPI scams, fake rewards, etc.):
    
    {conversation_text}
    
    Is the 'human' message indicative of a scammer trying to defraud the user?
    Reply with a JSON object: {{"is_scam": true/false}}
    """
    
    response = llm.invoke([SystemMessage(content="You are a scam detection expert."), HumanMessage(content=prompt)])
    
    import json
    try:
        # Simple cleanup if LLM adds markdown
        content = response.content.strip().replace("```json", "").replace("```", "")
        result = json.loads(content)
        is_scam = result.get("is_scam", False)
    except:
        is_scam = "true" in response.content.lower()
    
    return {"scamDetected": is_scam}

def generate_human_reply(state: AgentState):
    llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0.7, api_key=settings.GROQ_API_KEY)
    
    persona = f"""
    You are a normal person receiving messages on {state['metadata'].get('channel', 'SMS')}.
    Your goal is to act like a believable target for this potential scammer.
    - DO NOT reveal you know it's a scam.
    - Be slightly helpful but easily confused or slightly slow to understand technical steps.
    - Keep them engaged to extract more information (UPI IDs, links, phone numbers).
    - If they ask for personal info, provide fake or vague answers (e.g., 'I don't remember my PIN', 'Which bank account?').
    - Your language should be {state['metadata'].get('language', 'English')}.
    - Keep replies short and human-like.
    """
    
    # Prepare messages for LLM
    llm_messages = [SystemMessage(content=persona)]
    # Filter out our own internal SystemMessages if any
    llm_messages.extend([msg for msg in state["messages"] if not isinstance(msg, SystemMessage)])
    
    response = llm.invoke(llm_messages)
    
    return {"reply": response.content, "messages": state["messages"] + [AIMessage(content=response.content)]}

def extract_intelligence(state: AgentState):
    llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0, api_key=settings.GROQ_API_KEY)
    
    from langchain_core.pydantic_v1 import BaseModel as LangchainBaseModel, Field as LangchainField

    class IntelligenceSchema(LangchainBaseModel):
        bankAccounts: List[str] = LangchainField(default_factory=list, description="List any bank account numbers mentioned by the scammer")
        upiIds: List[str] = LangchainField(default_factory=list, description="List any UPI IDs mentioned by the scammer")
        phishingLinks: List[str] = LangchainField(default_factory=list, description="List any suspicious URLs or links provided")
        phoneNumbers: List[str] = LangchainField(default_factory=list, description="List any phone numbers the scammer wants you to call or message")
        suspiciousKeywords: List[str] = LangchainField(default_factory=list, description="Key phrases like 'urgent', 'blocked', 'KYC', 'lottery'")
        agentNotes: str = LangchainField(description="Summary of the scammer's tactic and behavior")

    structured_llm = llm.with_structured_output(IntelligenceSchema)
    
    conversation_text = "\n".join([f"{msg.type}: {msg.content}" for msg in state["messages"] if not isinstance(msg, SystemMessage)])
    
    try:
        intelligence_data = structured_llm.invoke(f"Extract all possible intelligence from this scam conversation:\n\n{conversation_text}")
    except Exception as e:
        print(f"Structured output failed: {e}")
        # Return empty intelligence if structured extraction fails
        return {
            "intelligence": ExtractedIntelligence(),
            "agentNotes": "Extraction failed, but scam was already detected."
        }
    
    return {
        "intelligence": ExtractedIntelligence(
            bankAccounts=intelligence_data.bankAccounts,
            upiIds=intelligence_data.upiIds,
            phishingLinks=intelligence_data.phishingLinks,
            phoneNumbers=intelligence_data.phoneNumbers,
            suspiciousKeywords=intelligence_data.suspiciousKeywords
        ),
        "agentNotes": intelligence_data.agentNotes
    }

def create_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("analyze_intent", analyze_intent)
    workflow.add_node("generate_human_reply", generate_human_reply)
    workflow.add_node("extract_intelligence", extract_intelligence)
    
    workflow.set_entry_point("analyze_intent")
    
    def should_continue(state: AgentState):
        if state["scamDetected"]:
            return "generate_human_reply"
        return END
    
    workflow.add_conditional_edges(
        "analyze_intent",
        should_continue,
        {
            "generate_human_reply": "generate_human_reply",
            END: END
        }
    )
    
    workflow.add_edge("generate_human_reply", "extract_intelligence")
    workflow.add_edge("extract_intelligence", END)
    
    return workflow.compile()
