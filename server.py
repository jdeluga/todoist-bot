from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from todoist_api_python.api import TodoistAPI
import os

app = FastAPI()

# Włączamy CORS
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

# Obsługa preflight (OPTIONS) dla /add_task
@app.options("/add_task")
async def options_add_task():
    return JSONResponse(content={"status": "ok"})

@app.post("/add_task")
async def add_task(request: Request):
    """
    Endpoint do dodawania zadań do Todoist.
    """
    data = await request.json()
    content = data.get("content")
    due = data.get("due")
    priority = data.get("priority", 1)

    if not content:
        return {"status": "error", "message": "Brak treści zadania"}

    try:
        task = api.add_task(
            content=content,
            due_string=due,
            priority=priority
        )
        return {"status": "success", "task": task.content}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def root():
    return {"status": "ok", "message": "Todoist bot działa!"}
