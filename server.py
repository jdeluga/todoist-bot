from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import re
import traceback
import dateparser

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TODOIST_TOKEN = os.getenv("TODOIST_API_TOKEN")

def clean_command(text: str) -> str:
    text = re.sub(r"\b(przypomnij mi|dodaj|umów|zrób|proszę|muszę|chcę)\b", "", text, flags=re.IGNORECASE)
    return text.strip()

def split_tasks(text: str):
    parts = re.split(r"\bi\b|,| oraz | potem | następnie ", text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]

def parse_task(text: str):
    priority = 1
    project = None
    due = None

    # priorytet
    pri_match = re.search(r"priorytet\s*(\d+)", text, re.IGNORECASE)
    if pri_match:
        priority = max(1, min(4, int(pri_match.group(1))))
        text = re.sub(r"priorytet\s*\d+", "", text, flags=re.IGNORECASE)
    if "priorytet wysoki" in text.lower():
        priority = 4
        text = text.replace("priorytet wysoki", "")
    elif "priorytet średni" in text.lower():
        priority = 2
        text = text.replace("priorytet średni", "")
    elif "priorytet niski" in text.lower():
        priority = 1
        text = text.replace("priorytet niski", "")

    # projekt
    proj_match = re.search(r"projekt\s+([a-zA-ZąćęłńóśżźĄĆĘŁŃÓŚŻŹ0-9]+)", text, re.IGNORECASE)
    if proj_match:
        project = proj_match.group(1).capitalize()
        text = re.sub(r"projekt\s+[a-zA-ZąćęłńóśżźĄĆĘŁŃÓŚŻŹ0-9]+", "", text, flags=re.IGNORECASE)

    # data (reszta tekstu)
    date_match = dateparser.parse(
        text,
        languages=['pl'],
        settings={'PREFER_DATES_FROM': 'future'}
    )
    if date_match:
        due = date_match.strftime("%Y-%m-%dT%H:%M:%S")

    return {"content": text.strip(), "priority": priority, "project": project, "due": due}

async def ensure_project_id(client, project_name):
    try:
        headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
        resp = await client.get("https://api.todoist.com/rest/v2/projects", headers=headers)
        print("Projects list status:", resp.status_code)
        if resp.status_code == 200:
            project_list = resp.json()
            for p in project_list:
                if p["name"].lower() == project_name.lower():
                    print(f"Project found: {p['name']} ({p['id']})")
                    return p["id"]
            print(f"Project '{project_name}' not found. Creating...")
            new_proj = await client.post(
                "https://api.todoist.com/rest/v2/projects",
                headers=headers,
                json={"name": project_name}
            )
            print("New project creation response:", new_proj.status_code, new_proj.text)
            if new_proj.status_code == 200:
                return new_proj.json()["id"]
        else:
            print("Error fetching projects:", resp.text)
    except Exception as e:
        print("Error in ensure_project_id:", e)
        traceback.print_exc()
    return None

@app.post("/from_chatgpt")
@app.get("/from_chatgpt")
async def from_chatgpt(request: Request):
    try:
        command = None
        if request.method == "POST":
            try:
                data = await request.json()
                command = data.get("command")
            except:
                pass
        if not command:
            command = request.query_params.get("text")
        if not command:
            return {"status": "error", "message": "Brak komendy"}

        command = clean_command(command)
        tasks_texts = split_tasks(command)

        results = []
        async with httpx.AsyncClient() as client:
            for task_text in tasks_texts:
                parsed = parse_task(task_text)
                print("Parsed task:", parsed)
                payload = {
                    "content": parsed["content"],
                    "priority": parsed["priority"]
                }
                if parsed["due"]:
                    payload["due_datetime"] = parsed["due"]
                if parsed["project"]:
                    proj_id = await ensure_project_id(client, parsed["project"])
                    if proj_id:
                        payload["project_id"] = proj_id
                        print(f"Assigned to project ID: {proj_id}")
                    else:
                        print(f"Project '{parsed['project']}' could not be resolved")

                headers = {
                    "Authorization": f"Bearer {TODOIST_TOKEN}",
                    "Content-Type": "application/json"
                }
                print("Sending task payload:", payload)
                r = await client.post("https://api.todoist.com/rest/v2/tasks", json=payload, headers=headers)
                print("Task creation response:", r.status_code, r.text)
                if r.status_code in [200, 204]:
                    task_data = r.json()
                    results.append({
                        "task": parsed["content"],
                        "project": parsed["project"],
                        "due": parsed["due"],
                        "priority": parsed["priority"],
                        "url": task_data.get("url", ""),
                        "status": "success"
                    })
                else:
                    results.append({
                        "task": parsed["content"],
                        "status": "error",
                        "todoist_response": r.text
                    })

        return {"added_tasks": results}
    except Exception as e:
        print("Fatal error in /from_chatgpt:", e)
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
