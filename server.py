from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import dateparser
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TODOIST_TOKEN = os.getenv("TODOIST_API_TOKEN")

PROJECT_KEYWORDS = {
    "kupić": "Zakupy",
    "zamówić": "Zakupy",
    "zadzwonić": "Kontakty",
    "napisać": "Kontakty",
    "spotkanie": "Spotkania",
    "umówić": "Spotkania",
}
LABEL_KEYWORDS = {
    "zadzwonić": "telefon",
    "telefon": "telefon",
    "spotkanie": "meeting",
    "umówić": "meeting",
    "email": "email",
    "wysłać": "email"
}

def clean_command(text: str) -> str:
    text = re.sub(r"\b(przypomnij mi|dodaj|umów|zrób|proszę|muszę|chcę)\b", "", text, flags=re.IGNORECASE)
    return text.strip()

def split_tasks(text: str):
    parts = re.split(r"\bi\b|,| oraz | potem | następnie ", text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]

def infer_project(content: str):
    for keyword, project in PROJECT_KEYWORDS.items():
        if keyword in content.lower():
            return project
    return None

def infer_labels(content: str):
    labels = []
    for keyword, label in LABEL_KEYWORDS.items():
        if keyword in content.lower():
            labels.append(label)
    return labels

def parse_task(text: str):
    priority = 1
    project = None
    due = None
    labels = []

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

    proj_match = re.search(r"projekt\s+([a-zA-ZąćęłńóśżźĄĆĘŁŃÓŚŻŹ]+)", text, re.IGNORECASE)
    if proj_match:
        project = proj_match.group(1).capitalize()
        text = re.sub(r"projekt\s+[a-zA-ZąćęłńóśżźĄĆĘŁŃÓŚŻŹ]+", "", text, flags=re.IGNORECASE)

    date_match = dateparser.parse(
        text,
        languages=['pl'],
        settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': None}
    )
    if date_match:
        due = date_match.strftime("%Y-%m-%d %H:%M")

    content = text.strip()
    if not project:
        project = infer_project(content)
    labels = infer_labels(content)

    return {"content": content, "priority": priority, "project": project, "due": due, "labels": labels}

async def ensure_project_id(client, project_name):
    headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
    resp = await client.get("https://api.todoist.com/rest/v2/projects", headers=headers)
    if resp.status_code == 200:
        project_list = resp.json()
        for p in project_list:
            if p["name"].lower() == project_name.lower():
                return p["id"]
        new_proj = await client.post(
            "https://api.todoist.com/rest/v2/projects",
            headers=headers,
            json={"name": project_name}
        )
        if new_proj.status_code == 200:
            return new_proj.json()["id"]
    return None

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
        command = request.query_params.get("text")
    if not command:
        return {"status": "error", "message": "Brak komendy"}

    command = clean_command(command)
    tasks_texts = split_tasks(command)

    results = []
    async with httpx.AsyncClient() as client:
        for task_text in tasks_texts:
            parsed = parse_task(task_text)
            payload = {
                "content": parsed["content"],
                "priority": parsed["priority"]
            }
            if parsed["due"]:
                payload["due_string"] = parsed["due"]
            if parsed["labels"]:
                payload["labels"] = parsed["labels"]
            if parsed["project"]:
                proj_id = await ensure_project_id(client, parsed["project"])
                if proj_id:
                    payload["project_id"] = proj_id

            headers = {
                "Authorization": f"Bearer {TODOIST_TOKEN}",
                "Content-Type": "application/json"
            }
            r = await client.post("https://api.todoist.com/rest/v2/tasks", json=payload, headers=headers)
            if r.status_code in [200, 204]:
                task_data = r.json()
                results.append({
                    "task": parsed["content"],
                    "due": parsed["due"],
                    "project": parsed["project"],
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
