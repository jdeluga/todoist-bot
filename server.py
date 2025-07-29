from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import dateparser
import re

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TODOIST_TOKEN = os.getenv("TODOIST_API_TOKEN")

@app.get("/")
def home():
    return {"status": "ok", "message": "Todoist bot działa!"}

@app.post("/from_chatgpt")
@app.get("/from_chatgpt")
async def from_chatgpt(request: Request):
    command = None
    if request.method == "POST":
        try:
            data = await request.json()
            command = data.get("command")
        except:
            pass
    if not command:
        # Obsługa GET z parametrem
        command = request.query_params.get("text")

    if not command:
        return {"status": "error", "message": "Brak komendy"}

    # --- Parser ---
    priority = 1
    project = None
    due = None

    # Wyszukaj priorytet
    pri_match = re.search(r"priorytet\s*(\d+)", command, re.IGNORECASE)
    if pri_match:
        priority = max(1, min(4, int(pri_match.group(1))))
        command = re.sub(r"priorytet\s*\d+", "", command, flags=re.IGNORECASE)

    # Wyszukaj projekt
    proj_match = re.search(r"projekt\s+(\w+)", command, re.IGNORECASE)
    if proj_match:
        project = proj_match.group(1).capitalize()
        command = re.sub(r"projekt\s+\w+", "", command, flags=re.IGNORECASE)

    # Wyszukaj datę
    date_match = dateparser.parse(command, languages=['pl'])
    if date_match:
        due = date_match.strftime("%Y-%m-%d %H:%M")

    # Treść zadania (bez priorytetu, projektu i daty)
    content = command.strip()

    # --- Przygotowanie payloadu ---
    todoist_payload = {
        "content": content,
        "priority": priority,
    }
    if due:
        todoist_payload["due_string"] = due

    # Jeśli projekt podany - pobierz ID projektu
    if project:
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
            resp = await client.get("https://api.todoist.com/rest/v2/projects", headers=headers)
            if resp.status_code == 200:
                for p in resp.json():
                    if p["name"].lower() == project.lower():
                        todoist_payload["project_id"] = p["id"]

    # --- Wyślij do Todoist ---
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {TODOIST_TOKEN}",
            "Content-Type": "application/json"
        }
        r = await client.post("https://api.todoist.com/rest/v2/tasks", json=todoist_payload, headers=headers)

    if r.status_code in [200, 204]:
        return {"status": "success", "task": content}
    else:
        return {"status": "error", "message": f"{r.status_code}: {r.text}"}
