from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from todoist_api_python.api import TodoistAPI
import os

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pobieramy token
API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("Brak API_TOKEN! Ustaw go w Environment Variables na Render.")

api = TodoistAPI(API_TOKEN)

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
    project_id = data.get("project_id")

    if not content:
        return {"status": "error", "message": "Brak treści zadania"}

    try:
        task = api.add_task(
            content=content,
            due_string=due,
            priority=priority,
            project_id=project_id
        )
        return {"status": "success", "task": task.content}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Lista projektów
@app.get("/projects")
async def get_projects():
    try:
        projects = api.get_projects()
        return [{"id": p.id, "name": p.name} for p in projects]
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Root
@app.get("/")
def root():
    return {"status": "ok", "message": "Todoist bot działa!"}
