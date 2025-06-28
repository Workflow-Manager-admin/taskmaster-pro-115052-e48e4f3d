from fastapi import FastAPI, Depends, HTTPException, status, Query, Path
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, Field
from .database import engine, Base, SessionLocal
from .models import Task


app = FastAPI(
    title="TaskMaster Pro API",
    version="1.0.0",
    description=(
        "REST API backend for the TaskMaster Pro app. "
        "Provides endpoints for task CRUD operations."
    ),
    openapi_tags=[
        {
            "name": "Tasks",
            "description": (
                "Operations with tasks: create, list/filter, update, and delete."
            )
        }
    ]
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Pydantic Models ---


# PUBLIC_INTERFACE
class TaskBase(BaseModel):
    title: str = Field(..., description="Title of the task")
    description: Optional[str] = Field(
        None, description="Description of the task"
    )
    category: Optional[str] = Field(
        None, description="Category for grouping/filtering tasks"
    )
    priority: Optional[int] = Field(
        None, description="Priority of the task (1=highest, 5=lowest)"
    )
    due_date: Optional[datetime] = Field(
        None, description="Due date (ISO 8601 format)"
    )
    completed: Optional[bool] = Field(
        False, description="Completion status"
    )


# PUBLIC_INTERFACE
class TaskCreate(TaskBase):
    title: str = Field(..., description="Title of the task")


# PUBLIC_INTERFACE
class TaskUpdate(BaseModel):
    title: Optional[str] = Field(
        None, description="Title of the task"
    )
    description: Optional[str] = Field(
        None, description="Description of the task"
    )
    category: Optional[str] = Field(
        None, description="Category for grouping/filtering tasks"
    )
    priority: Optional[int] = Field(
        None, description="Priority of the task (1=highest, 5=lowest)"
    )
    due_date: Optional[datetime] = Field(
        None, description="Due date (ISO 8601 format)"
    )
    completed: Optional[bool] = Field(
        None, description="Completion status"
    )


# PUBLIC_INTERFACE
class TaskOut(TaskBase):
    id: int = Field(..., description="Task ID")

    class Config:
        from_attributes = True


@app.on_event("startup")
def on_startup():
    """
    Ensure all database tables are created at application startup.
    """
    Base.metadata.create_all(bind=engine)


@app.get("/", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}


# ---- CRUD Endpoints ----


# PUBLIC_INTERFACE
@app.get(
    "/api/tasks",
    response_model=List[TaskOut],
    tags=["Tasks"],
    summary="List/filter all tasks"
)
def list_tasks(
    category: Optional[str] = Query(
        None, description="Filter tasks by category"
    ),
    completed: Optional[bool] = Query(
        None, description="Filter by completion status (true/false)"
    ),
    q: Optional[str] = Query(
        None, description="Search substring in title or description"
    ),
    db: Session = Depends(get_db)
):
    """
    Retrieve all tasks, with optional filtering by category, completion, or search term.
    """
    tasks_query = db.query(Task)
    if category is not None:
        tasks_query = tasks_query.filter(Task.category == category)
    if completed is not None:
        tasks_query = tasks_query.filter(Task.completed == completed)
    if q:
        search = f"%{q}%"
        tasks_query = tasks_query.filter(
            (Task.title.ilike(search)) | (Task.description.ilike(search))
        )
    return (
        tasks_query
        .order_by(Task.due_date.isnot(None), Task.due_date.asc())
        .all()
    )


# PUBLIC_INTERFACE
@app.post(
    "/api/tasks",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Tasks"],
    summary="Create a new task"
)
def create_task(task_in: TaskCreate, db: Session = Depends(get_db)):
    """
    Create a new task and save to the database.
    """
    task_obj = Task(
        title=task_in.title,
        description=task_in.description,
        category=task_in.category,
        priority=task_in.priority,
        due_date=task_in.due_date,
        completed=task_in.completed or False,
    )
    db.add(task_obj)
    db.commit()
    db.refresh(task_obj)
    return task_obj


# PUBLIC_INTERFACE
@app.put(
    "/api/tasks/{task_id}",
    response_model=TaskOut,
    tags=["Tasks"],
    summary="Update a task by ID"
)
def update_task(
    task_id: int = Path(..., description="Task ID"),
    updates: TaskUpdate = ...,
    db: Session = Depends(get_db)
):
    """
    Update a task by its ID. Only provided fields will be updated.
    Returns the updated object or 404 if not found.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )
    for field, value in updates.dict(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


# PUBLIC_INTERFACE
@app.delete(
    "/api/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Tasks"],
    summary="Delete task by ID"
)
def delete_task(
    task_id: int = Path(..., description="Task ID"),
    db: Session = Depends(get_db)
):
    """
    Delete a task by its ID. Returns 204 No Content on success, 404 if not found.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )
    db.delete(task)
    db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)
