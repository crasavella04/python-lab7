async def create_task(client, owner_id: int, **fields) -> dict:
    payload = {"title": "Task", "owner_id": owner_id, **fields}
    response = await client.post("/tasks", json=payload)
    assert response.status_code == 201
    return response.json()


async def test_create_task(client, user):
    response = await client.post(
        "/tasks",
        json={"title": "Write tests", "description": "pytest", "owner_id": user["id"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Write tests"
    assert body["description"] == "pytest"
    assert body["done"] is False
    assert body["owner_id"] == user["id"]


async def test_create_task_unknown_owner(client):
    response = await client.post("/tasks", json={"title": "Orphan", "owner_id": 999})

    assert response.status_code == 404
    assert response.json()["detail"] == "Owner not found"


async def test_create_task_empty_title(client, user):
    response = await client.post("/tasks", json={"title": "", "owner_id": user["id"]})

    assert response.status_code == 422


async def test_list_tasks_filter_done_and_pagination(client, user):
    # 6 задач: чётные выполнены, нечётные нет
    for i in range(1, 7):
        await create_task(client, user["id"], title=f"Task {i}", done=i % 2 == 0)

    done = await client.get("/tasks", params={"done": True})
    assert done.status_code == 200
    assert [t["title"] for t in done.json()] == ["Task 2", "Task 4", "Task 6"]

    not_done = await client.get("/tasks", params={"done": False})
    assert [t["title"] for t in not_done.json()] == ["Task 1", "Task 3", "Task 5"]

    page = await client.get("/tasks", params={"limit": 2, "offset": 2})
    assert [t["title"] for t in page.json()] == ["Task 3", "Task 4"]

    done_page = await client.get(
        "/tasks", params={"done": True, "limit": 2, "offset": 1}
    )
    assert [t["title"] for t in done_page.json()] == ["Task 4", "Task 6"]


async def test_list_tasks_invalid_limit(client):
    response = await client.get("/tasks", params={"limit": 0})

    assert response.status_code == 422


async def test_patch_updates_only_passed_fields(client, user):
    task = await create_task(
        client, user["id"], title="Original", description="Keep me"
    )

    response = await client.patch(f"/tasks/{task['id']}", json={"done": True})

    assert response.status_code == 200
    body = response.json()
    assert body["done"] is True
    assert body["title"] == "Original"
    assert body["description"] == "Keep me"
    assert body["created_at"] == task["created_at"]

    # изменение действительно сохранено в БД
    stored = await client.get(f"/tasks/{task['id']}")
    assert stored.json() == body


async def test_patch_null_title_rejected(client, user):
    task = await create_task(client, user["id"])

    response = await client.patch(f"/tasks/{task['id']}", json={"title": None})

    assert response.status_code == 422


async def test_delete_then_get_returns_404(client, user):
    task = await create_task(client, user["id"])

    deleted = await client.delete(f"/tasks/{task['id']}")
    assert deleted.status_code == 204

    response = await client.get(f"/tasks/{task['id']}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


async def test_delete_unknown_task(client):
    response = await client.delete("/tasks/999")

    assert response.status_code == 404


async def test_process_time_header(client):
    response = await client.get("/tasks")

    assert response.status_code == 200
    assert "X-Process-Time" in response.headers
    assert float(response.headers["X-Process-Time"]) >= 0
