#!/usr/bin/env python3
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .supervisor import Supervisor
from .task_manager import TaskManager
from .schemas.unified_models import TaskStatus, AgentType, ComponentArea, TaskPriority

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="DevPro Orchestrator API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared instances
# Note: Supervisor and TaskManager are initialized lazily or on startup
supervisor: Optional[Supervisor] = None
task_manager = TaskManager()

class TaskCreate(BaseModel):
    title: str
    description: str
    component_area: str
    priority: str = "medium"
    phase: str = "development"
    time_estimate_hours: float = 1.0

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    component_area: str
    priority: str

@app.on_event("startup")
async def startup_event():
    global supervisor
    supervisor = Supervisor()
    logger.info("API started and Supervisor initialized")

@app.on_event("shutdown")
async def shutdown_event():
    if supervisor:
        await supervisor.close()
    logger.info("API shut down")

@app.get("/status")
async def get_status():
    if not supervisor:
        return {"status": "initializing"}
    return await supervisor.get_agent_status()

@app.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(status: Optional[str] = None):
    try:
        if status:
            tasks = task_manager.get_tasks_by_status(status)
        else:
            # Default to all tasks for the UI dashboard
            tasks = task_manager.get_tasks_by_status("all")
        return tasks
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks", response_model=TaskResponse)
async def create_task(task: TaskCreate):
    try:
        # Map user-facing component area names to enum values
        component_map = {
            "research": "task",
            "core": "architecture",
            "integrations": "services",
            "ui": "ui",
            "testing": "testing",
            "documentation": "documentation",
            "architecture": "architecture",
            "services": "services"
        }
        area = task.component_area.lower()
        component_value = component_map.get(area, area)

        now = datetime.now(tz=timezone.utc)
        new_task = task_manager.create_task({
            "title": task.title,
            "description": task.description,
            "component_area": ComponentArea(component_value),
            "priority": TaskPriority(task.priority.lower()),
            "phase": 1,
            "time_estimate_hours": task.time_estimate_hours,
            "status": TaskStatus.NOT_STARTED,
            "created_at": now,
            "updated_at": now,
        })
        return {
            "id": new_task.id,
            "title": new_task.title,
            "description": new_task.description,
            "status": new_task.status,
            "component_area": new_task.component_area,
            "priority": new_task.priority,
        }
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks/{task_id}")
async def get_task(task_id: int):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    deleted = task_manager.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete task")
    return {"message": f"Task {task_id} deleted successfully"}

@app.post("/tasks/{task_id}/execute")
async def execute_task(task_id: int, background_tasks: BackgroundTasks):
    if not supervisor:
        raise HTTPException(status_code=503, detail="Supervisor not initialized")
    
    # Check if task exists
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # We run the task in the foreground for simplicity in this example
    # but for a real UI, background execution with status polling is better.
    # For now, we'll return the result directly.
    try:
        result = await supervisor.execute_task(task_id)
        return result
    except Exception as e:
        logger.error(f"Error executing task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
