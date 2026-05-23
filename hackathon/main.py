import os
import requests
import json
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
from glia.brain import GliaBrain
import uvicorn
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load env variables
load_dotenv()

app = FastAPI(
    title="GLIA Memory API",
    description="Cloud-Native Holographic Memory for AI Agents",
    version="1.2.0"
)

# Configuration
GITLAB_TOKEN = os.environ.get("GITLAB_PERSONAL_ACCESS_TOKEN")
GITLAB_API_URL = os.environ.get("GITLAB_API_URL", "https://gitlab.com/api/v4")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GLIA_MODEL = os.environ.get("GLIA_MODEL", "gemini-3.5-flash")

# Initialize Clients
# If GEMINI_API_KEY is not set, the SDK will attempt to use Vertex AI via application default credentials
if not GEMINI_API_KEY:
    print("🚀 Initializing with Vertex AI (Native Google Cloud Auth)")
    ai = genai.Client(vertexai=True, location="us-central1")
else:
    print("🔑 Initializing with Google AI Studio (API Key)")
    ai = genai.Client(api_key=GEMINI_API_KEY)

workspace = Path(__file__).parent.parent # Point to project root
brain = GliaBrain(workspace=workspace, model=GLIA_MODEL, api_key=GEMINI_API_KEY)

if not brain.is_initialized:
    brain.init()

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

class LearnRequest(BaseModel):
    content: str
    source: Optional[str] = "cloud-api"

@app.get("/")
async def root():
    return {"status": "online", "engine": "GLIA Holographic Memory", "version": "v2"}

@app.post("/recall")
async def recall(request: QueryRequest):
    """Retrieves associative context from GLIA memory."""
    try:
        result = brain.recall(request.query, top_k=request.top_k)
        return {
            "context": result["context"],
            "nodes": result["activated_nodes"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/learn")
async def learn(request: LearnRequest):
    """Teaches new knowledge to the holographic substrate."""
    try:
        result = brain.learn(request.content, source=request.source)
        return {
            "summary": result.get("summary"),
            "concepts": result.get("concepts")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync-memory")
async def sync_memory(file: UploadFile = File(...)):
    """Replaces current server memory with a local .db file."""
    try:
        # Close existing storage connection to prevent locks
        if brain._storage:
            brain._storage.close()
            brain._storage = None
            
        target_path = brain.glia_path / "memory.db"
        brain.glia_path.mkdir(parents=True, exist_ok=True)
        
        # Save the uploaded file
        with open(target_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Reset and reload the brain state
        brain._loaded = False
        brain.load() # This re-populates brain.substrate
        
        return {
            "status": "success",
            "message": "Memory database updated",
            "stats": brain.stats()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def stats():
    """Returns memory statistics."""
    return brain.stats()

# --- GitLab Automation Logic ---

def fetch_gitlab_mr_diff(project_id: int, mr_iid: int) -> str:
    """Fetches the diff of a Merge Request from GitLab."""
    url = f"{GITLAB_API_URL}/projects/{project_id}/merge_requests/{mr_iid}/changes"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return f"Error fetching diff: {response.text}"
    
    changes = response.json().get("changes", [])
    diff_text = ""
    for change in changes:
        diff_text += f"File: {change['new_path']}\n{change['diff']}\n\n"
    return diff_text

def post_gitlab_comment(project_id: int, mr_iid: int, body: str):
    """Posts a comment to the Merge Request."""
    url = f"{GITLAB_API_URL}/projects/{project_id}/merge_requests/{mr_iid}/notes"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    requests.post(url, headers=headers, json={"body": body})

async def run_autonomous_review(project_id: int, mr_iid: int):
    """The Agentic Loop: Recall Memory -> Reason -> Act."""
    print(f"🎬 Starting autonomous review for MR !{mr_iid} in project {project_id}")
    
    # 1. Fetch the actual code changes
    diff = fetch_gitlab_mr_diff(project_id, mr_iid)
    
    # 2. Consult GLIA Memory (Local to this container)
    memory_result = brain.recall(diff, top_k=3)
    historical_context = memory_result.get("context", "No relevant history found.")
    
    # 3. Ask Gemini to reason and decide
    prompt = f"""
    You are a Senior Tech Lead. Perform an automated review of this GitLab Merge Request.
    
    CODE CHANGES:
    {diff[:5000]}
    
    HISTORICAL CONTEXT FROM GLIA MEMORY:
    {historical_context}
    
    If the code violates past architectural rules or repeats known bugs, 
    provide a firm technical rejection. Otherwise, provide a brief approval.
    """
    
    response = ai.models.generate_content(
        model=GLIA_MODEL,
        contents=prompt
    )
    
    # 4. Post the decision back to GitLab
    final_comment = f"🤖 **GLIA Tech Lead Review**\n\n{response.text}"
    post_gitlab_comment(project_id, mr_iid, final_comment)
    print(f"✅ Review posted to GitLab for MR !{mr_iid}")

async def learn_from_merged_mr(project_id: int, mr_iid: int):
    """Learns from changes after a Merge Request has been merged."""
    print(f"🧠 MR !{mr_iid} merged! Learning changes...")
    diff = fetch_gitlab_mr_diff(project_id, mr_iid)
    if diff and not diff.startswith("Error"):
        try:
            result = brain.learn(
                content=f"Approved Changes in MR !{mr_iid}:\n\n{diff}",
                source=f"gitlab-mr-{mr_iid}-merged"
            )
            print(f"✅ Knowledge integrated for MR !{mr_iid}: {result.get('concepts')}")
        except Exception as e:
            print(f"❌ Error learning from MR !{mr_iid}: {e}")

@app.post("/webhook/gitlab")
async def gitlab_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receives Merge Request events from GitLab."""
    data = await request.json()
    
    # Check if it's a Merge Request event
    object_kind = data.get("object_kind")
    if object_kind == "merge_request":
        attr = data.get("object_attributes", {})
        action = attr.get("action")
        project_id = data.get("project", {}).get("id")
        mr_iid = attr.get("iid")
        
        # Case 1: Autonomous Review (Open/Update)
        if action in ["open", "reopen", "update"]:
            background_tasks.add_task(run_autonomous_review, project_id, mr_iid)
            return {"status": "accepted", "message": "Review task scheduled"}

        # Case 2: Autonomous Learning (Merge)
        if action == "merge":
            background_tasks.add_task(learn_from_merged_mr, project_id, mr_iid)
            return {"status": "accepted", "message": "Learning task scheduled"}
            
    return {"status": "ignored"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
