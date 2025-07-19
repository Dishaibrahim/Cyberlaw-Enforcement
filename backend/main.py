import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


from .adk_agents import ADKLlm, firestore_tool
from .orchestrator import CourtroomOrchestrator

app_id = os.environ.get('__app_id', 'cyberlaw-app-dev')


active_courtroom_sessions: Dict[str, CourtroomOrchestrator] = {}


# Pydantic models for request and response validation
class FlagPostRequest(BaseModel):
    postContent: str
    victimInfo: str
    userId: str
    postLink: Optional[str] = None
    victimEthAddress: Optional[str] = None # New: Optional ETH address for victim

class StartCourtroomRequest(BaseModel):
    case_id: str


app = FastAPI()

# Configure CORS middleware
origins = [
    "http://localhost:3000", 
    "http://127.0.0.1:3000",
  
    "chrome-extension://*", # Allow your Chrome extension to connect
    "moz-extension://*", # Allow Firefox extension to connect
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize a global LLM for initial analysis agent
initial_llm_agent = ADKLlm(model_name="gemini-2.0-flash")


@app.post("/flag_post")
async def flag_post_endpoint(request: FlagPostRequest):
    """
    Endpoint to trigger the initial multi-agent cyber law analysis.
    Orchestrates calls to simulated initial agents (Gemini) and updates Firestore.
    """
    if firestore_tool.db is None:
        raise HTTPException(status_code=500, detail="Firestore client not initialized. Check backend logs.")

    case_id = f"{int(datetime.now().timestamp())}-{request.userId}"
    current_case = {
        "id": case_id,
        "timestamp": datetime.now().isoformat(),
        "postContent": request.postContent,
        "postLink": request.postLink, # Store the provided link for reference
        "victimInfo": request.victimInfo,
        "victimEthAddress": request.victimEthAddress, # Store victim's ETH address
        "userId": request.userId,
        "status": "Pending Initial Analysis",
        "analysis": {},
        "councilDecision": {}, # This will be filled later by Judge Agent
        "ledgerEntry": {}, # This will be filled later by Judge Agent
        "appId": app_id # To ensure data is stored under the correct app ID
    }

    try:
        # --- Agent 1: Post Analyzer Agent ---
        analysis_prompt = f"""You are an AI specializing in cyber law. Analyze the following post content for potential violations of common cyber laws (e.g., harassment, defamation, intellectual property, hate speech). Assume you have access to a comprehensive database of cyber laws. Provide a brief assessment, identify potential violations, and cite which *types* of cyber laws might apply.
        Post Content: "{request.postContent}"
        
        Provide the response in JSON format with the following schema:
        {{
            "isViolation": boolean,
            "violationType": "string (e.g., 'Harassment', 'Defamation', 'Hate Speech', 'IP Infringement', 'None')",
            "relevantLaws": "string (brief description of relevant cyber law types)",
            "assessmentSummary": "string (short summary of the assessment)"
        }}
        """
        analysis_schema = {
            "type": "OBJECT",
            "properties": {
                "isViolation": { "type": "BOOLEAN" },
                "violationType": { "type": "STRING" },
                "relevantLaws": { "type": "STRING" },
                "assessmentSummary": { "type": "STRING" }
            }
        }
        analysis_result = await initial_llm_agent.generate_content(analysis_prompt, response_schema=analysis_schema)
        
        if not isinstance(analysis_result, dict) or "error" in analysis_result:
            raise HTTPException(status_code=500, detail=f"Post Analyzer Agent failed: {analysis_result.get('error', 'Unknown Gemini error')}")

        current_case["analysis"] = analysis_result
        current_case["status"] = 'Violation Detected' if analysis_result["isViolation"] else 'No Violation - Initial Analysis'

        # Store the initial case details in Firestore
        fs_set_result = await firestore_tool.run(
            "set_doc",
            f"artifacts/{app_id}/public/data/cyberlawCases",
            case_id,
            current_case
        )
        print(f"Firestore initial set result: {fs_set_result}")

        if not analysis_result["isViolation"]:
            print('No violation detected during initial analysis. Case closed at this stage.')
            current_case["status"] = 'Case Closed - No Violation'
            await firestore_tool.run(
                "set_doc",
                f"artifacts/{app_id}/public/data/cyberlawCases",
                case_id,
                {"status": "Case Closed - No Violation"} # Update status
            )
            return {"status": "success", "message": "No violation detected. Case closed.", "case_id": case_id, "case_details": current_case}
        
        print("Violation detected. Ready for courtroom session.")
        return {"status": "success", "message": "Initial analysis complete. Violation detected. Ready for courtroom session.", "case_id": case_id, "case_details": current_case}

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Server error during initial processing: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.post("/start_courtroom_session")
async def start_courtroom_session_endpoint(request: StartCourtroomRequest):
    """
    Starts a new multi-agent courtroom session for a given case_id.
    """
    case_id = request.case_id
    if case_id in active_courtroom_sessions:
        raise HTTPException(status_code=409, detail=f"Courtroom session for case_id {case_id} is already active.")

    if firestore_tool.db is None:
        raise HTTPException(status_code=500, detail="Firestore client not initialized.")

    # Fetch initial case details from Firestore
    case_details_str = await firestore_tool.run(
        "get_doc",
        f"artifacts/{app_id}/public/data/cyberlawCases",
        case_id
    )
    if "error" in case_details_str or "Document not found" in case_details_str:
        raise HTTPException(status_code=404, detail=f"Case ID {case_id} not found in Firestore.")
    
    try:
        case_details = json.loads(case_details_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse case details from Firestore.")

    orchestrator = CourtroomOrchestrator(case_details=case_details)
    active_courtroom_sessions[case_id] = orchestrator

    # Run the courtroom session in the background
    asyncio.create_task(orchestrator.run_courtroom_session())

    return {"status": "success", "message": f"Courtroom session started for case_id {case_id}.", "case_id": case_id}


@app.get("/get_courtroom_updates")
async def get_courtroom_updates_endpoint(case_id: str):
    """
    Retrieves the current state of a courtroom session for real-time updates.
    """
    orchestrator = active_courtroom_sessions.get(case_id)
    if not orchestrator:
        raise HTTPException(status_code=404, detail=f"No active courtroom session found for case_id {case_id}.")

    return orchestrator.get_current_state_for_frontend()


# Root endpoint for health check
@app.get("/")
async def root():
    return {"message": "Cyber Law Multi-Agent Backend is running!"}
