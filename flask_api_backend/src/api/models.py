from sqlalchemy import Column, Integer, String, Boolean, DateTime
from .database import Base


# PUBLIC_INTERFACE
class Task(Base):
    """
    SQLAlchemy Task model representing a task in the database.
    Fields:
        id: int, primary key
        title: str, required
        description: str, optional
        category: str, optional (can be used for grouping/filtering)
        priority: int, optional (could be 1-5 or similar)
        due_date: datetime, optional (can be null)
        completed: bool, default False
    """
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    category = Column(String, nullable=True)
    priority = Column(Integer, nullable=True)
    due_date = Column(DateTime, nullable=True)
    completed = Column(Boolean, default=False)
