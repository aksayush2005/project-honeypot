from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import os
from dotenv import load_dotenv

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
print(f"API Key (first 10 chars): {groq_api_key[:10] if groq_api_key else 'NOT SET'}")

try:
    llm = ChatGroq(model_name="llama3-70b-8192", temperature=0, api_key=groq_api_key)
    response = llm.invoke([HumanMessage(content="Say hello")])
    print(f"SUCCESS: {response.content}")
except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
