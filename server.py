from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import httpx

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Token Todoist
API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("Brak API_TOKEN! Ustaw go w Environment Variables na Render.")

BASE_URL = "https://api.todoist.com/rest/v2"

# Preflight dla /add_task
@app.options("/add_task")
async def options_add_task():
    return JSONResponse(content={"status": "ok"})

# Dodawanie zadania
@app.post("/add_task")
async def add_task(request: Request):
    data = await request.json()
    content = data.get("content")
    due = data.get("due")
    priority = data.get("priority", 1)
    project_id = data.get("project_id") or None

    if not content or content.strip() == "":
        return {"status": "error", "message": "Treść zadania jest wymagana"}

    payload = {
        "content": content,
        "priority": priority
    }
    if due:
        payload["due_string"] = due
    if project_id:
        payload["project_id"] = project_id

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{BASE_URL}/tasks", json=payload, headers=headers)
            r.raise_for_status()
            return {"status": "success", "task": r.json()}
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"{e.response.status_code} {e.response.text}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Lista projektów
@app.get("/projects")
async def get_projects():
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{BASE_URL}/projects", headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"{e.response.status_code} {e.response.text}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

@app.get("/")
def root():
    return {"status": "ok", "message": "Todoist REST v2 działa!"}
