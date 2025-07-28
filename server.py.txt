from fastapi import FastAPI, Request
from todoist_api_python.api import TodoistAPI

app = FastAPI()
api = TodoistAPI(4af0aac48f7c410c57c4e5f2c706df6b15ffa0af)

@app.post("/add_task")
async def add_task(request: Request):
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
