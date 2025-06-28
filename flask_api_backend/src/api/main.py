from fastapi import FastAPI, Depends, HTTPException, status, Query, Path
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Union
from sqlalchemy.orm import Session
from datetime import datetime, timezone, date
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


def get_db():
    """Dependency to get DB session."""
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
class TaskCompletionUpdate(BaseModel):
    """Model for updating the completion status of a task."""
    completed: bool = Field(..., description="New completion status (true/false)")


# PUBLIC_INTERFACE
class TaskOut(TaskBase):
    id: int = Field(..., description="Task ID")
    overdue: bool = Field(
        ..., description="Is the task overdue (due_date < today and not completed)"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "title": "Finish code",
                "description": "Implement endpoint",
                "category": "Coding",
                "priority": 1,
                "due_date": "2024-07-11T12:00:00",
                "completed": False,
                "overdue": True
            }
        }


# Used for group-by response
class CategoryGroup(BaseModel):
    category: str = Field(..., description="Task Category")
    tasks: List[TaskOut] = Field(..., description="List of tasks in this category")


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
    response_model=Union[List[TaskOut], List[CategoryGroup]],
    tags=["Tasks"],
    summary="List/filter all tasks",
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
    group_by: Optional[str] = Query(
        None, description="Group tasks by field, e.g. 'category'"
    ),
    db: Session = Depends(get_db)
):
    """
    Retrieve all tasks, with optional filtering by category, completion, or search term.
    Use `group_by=category` to group results by category.
    Each task includes an 'overdue' field if the due date is before today and not completed.
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

    # Sorting: due soonest first, then nulls last
    tasks_db = (
        tasks_query
        .order_by(Task.due_date.isnot(None), Task.due_date.asc())
        .all()
    )

    today = date.today()

    def is_overdue(task_obj) -> bool:
        if not task_obj.due_date:
            return False
        # task_obj.due_date may be naive, interpret as local or UTC
        due = task_obj.due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        # Consider overdue if due date is before today and not completed
        return (due.date() < today) and (not task_obj.completed)

    # Convert to TaskOut + add overdue flag
    taskouts: List[TaskOut] = []
    for t in tasks_db:
        taskout = TaskOut(
            id=t.id,
            title=t.title,
            description=t.description,
            category=t.category,
            priority=t.priority,
            due_date=t.due_date,
            completed=t.completed,
            overdue=is_overdue(t),
        )
        taskouts.append(taskout)

    # Grouping support
    if group_by == "category":
        # Group tasks_out by their category
        grouped: Dict[Optional[str], List[TaskOut]] = {}
        for t in taskouts:
            cat = t.category if t.category is not None else "Uncategorized"
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(t)
        return [
            CategoryGroup(category=cat, tasks=ts)
            for cat, ts in grouped.items()
        ]
    else:
        return taskouts


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
    # Add overdue flag in response
    overdue = False
    if task_obj.due_date:
        task_due = task_obj.due_date
        if task_due.tzinfo is None:
            task_due = task_due.replace(tzinfo=timezone.utc)
        overdue = (
            (task_due.date() < date.today())
            and (not task_obj.completed)
        )
    return TaskOut(
        id=task_obj.id,
        title=task_obj.title,
        description=task_obj.description,
        category=task_obj.category,
        priority=task_obj.priority,
        due_date=task_obj.due_date,
        completed=task_obj.completed,
        overdue=overdue,
    )


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
    # Compute overdue flag for response
    overdue = False
    if task.due_date:
        task_due = task.due_date
        if task_due.tzinfo is None:
            task_due = task_due.replace(tzinfo=timezone.utc)
        overdue = (task_due.date() < date.today()) and (not task.completed)
    return TaskOut(
        id=task.id,
        title=task.title,
        description=task.description,
        category=task.category,
        priority=task.priority,
        due_date=task.due_date,
        completed=task.completed,
        overdue=overdue
    )


# PUBLIC_INTERFACE
@app.patch(
    "/api/tasks/{task_id}/completed",
    response_model=TaskOut,
    tags=["Tasks"],
    summary="Update a task's completed status",
    responses={
        200: {"description": "Task completion status updated"},
        404: {"description": "Task not found"},
        422: {"description": "Invalid input"},
    },
)
def update_task_completion(
    task_id: int = Path(..., description="Task ID"),
    status_in: TaskCompletionUpdate = ...,
    db: Session = Depends(get_db),
):
    """
    Update the 'completed' status of a task by its ID. Only the completed
    field will be modified.

    - **task_id**: The ID of the task to update.
    - **completed**: Boolean (true/false) representing new state.

    Returns the updated task or 404 if not found.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )
    task.completed = status_in.completed
    db.commit()
    db.refresh(task)
    # Compute overdue flag for response
    overdue = False
    if task.due_date:
        task_due = task.due_date
        if task_due.tzinfo is None:
            task_due = task_due.replace(tzinfo=timezone.utc)
        overdue = (task_due.date() < date.today()) and (not task.completed)
    return TaskOut(
        id=task.id,
        title=task.title,
        description=task.description,
        category=task.category,
        priority=task.priority,
        due_date=task.due_date,
        completed=task.completed,
        overdue=overdue,
    )


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
