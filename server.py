from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import httpx
import re
import dateparser

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Token i API URL
API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("Brak API_TOKEN! Ustaw go w Environment Variables na Render.")
BASE_URL = "https://api.todoist.com/rest/v2"

# Pobranie projektów (cache w pamięci)
async def fetch_projects():
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/projects", headers=headers)
        r.raise_for_status()
        return r.json()

# Parser komend
async def parse_task_command(text: str):
    projects = await fetch_projects()
    project_id = None

    # Rozpoznaj projekt
    for p in projects:
        if p['name'].lower() in text.lower():
            project_id = p['id']
            text = re.sub(p['name'], '', text, flags=re.IGNORECASE)
            break

    # Rozpoznaj priorytet
    priority = 1  # domyślny
    priority_map = {"1": 1, "2": 2, "3": 3, "4": 4,
                    "pierwszy": 1, "drugi": 2, "trzeci": 3, "czwarty": 4}
    for word, val in priority_map.items():
        if re.search(rf"\b{word}\b", text.lower()):
            priority = val
            text = re.sub(rf"\b{word}\b", '', text, flags=re.IGNORECASE)
            break

    # Rozpoznaj datę/godzinę
    due = None
    date_match = dateparser.parse(text, languages=['pl'])
    if date_match:
        due = date_match.strftime("%Y-%m-%d %H:%M")

    # Treść zadania
    content = text.strip()
    return content, due, priority, project_id

# Preflight
@app.options("/add_task")
async def options_add_task():
    return JSONResponse(content={"status": "ok"})

# Dodawanie zadania
@app.post("/add_task")
async def add_task(request: Request):
    data = await request.json()
    text = data.get("content")
    if not text or text.strip() == "":
        return {"status": "error", "message": "Treść zadania jest wymagana"}

    # Inteligentne parsowanie
    content, due, priority, project_id = await parse_task_command(text)

    payload = {"content": content, "priority": priority}
    if due:
        payload["due_string"] = due
    if project_id:
        payload["project_id"] = project_id

    headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        try:
            print("== Wysyłam do Todoist:", payload)
            r = await client.post(f"{BASE_URL}/tasks", json=payload, headers=headers)
            print("== Odpowiedź Todoist:", r.status_code, r.text)
            r.raise_for_status()
            return {"status": "success", "task": r.json()}
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"{e.response.status_code} {e.response.text}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Lista projektów
@app.get("/projects")
async def get_projects():
    try:
        return await fetch_projects()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def root():
    return {"status": "ok", "message": "Todoist bot z inteligentnym parserem działa!"}
