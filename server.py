from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
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

def clean_command(text: str) -> str:
    text = re.sub(r"\b(przypomnij mi|dodaj|umów|zrób|proszę|muszę|chcę)\b", "", text, flags=re.IGNORECASE)
    return text.strip()

def split_tasks(text: str):
    parts = re.split(r"\bi\b|,| oraz | potem | następnie ", text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]

def parse_task(text: str):
    priority = 1
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
    return {"content": text.strip(), "priority": priority}

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
            headers = {
                "Authorization": f"Bearer {TODOIST_TOKEN}",
                "Content-Type": "application/json"
            }
            r = await client.post("https://api.todoist.com/rest/v2/tasks", json=payload, headers=headers)
            if r.status_code in [200, 204]:
                task_data = r.json()
                results.append({
                    "task": parsed["content"],
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
