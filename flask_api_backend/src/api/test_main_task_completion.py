from fastapi.testclient import TestClient
from .main import app, Base, engine, SessionLocal
from .models import Task

client = TestClient(app)


def setup_function():
    # Recreate all tables, remove all existing rows
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # Seed one task
    db = SessionLocal()
    db.add(Task(
        title="Test task",
        description="desc",
        category="work",
        priority=2,
        due_date=None,
        completed=False,
    ))
    db.commit()
    db.close()


def teardown_function():
    Base.metadata.drop_all(bind=engine)


def test_patch_completion_status():
    # Fetch the only task's ID
    response = client.get("/api/tasks")
    assert response.status_code == 200
    data = response.json()
    task_id = data[0]["id"]
    assert not data[0]["completed"]

    # Mark as completed
    resp = client.patch(f"/api/tasks/{task_id}/completed", json={"completed": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed"]
    assert body["id"] == task_id

    # Fetch again and verify completed
    response2 = client.get("/api/tasks")
    assert response2.status_code == 200
    assert any(t["id"] == task_id and t["completed"] for t in response2.json())

    # Mark back to incomplete
    resp2 = client.patch(f"/api/tasks/{task_id}/completed", json={"completed": False})
    assert resp2.status_code == 200
    assert resp2.json()["completed"] is False

    # Try invalid id
    resp3 = client.patch("/api/tasks/999/completed", json={"completed": True})
    assert resp3.status_code == 404
    assert "not found" in resp3.json()["detail"]
