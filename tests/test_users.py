async def test_create_user(client):
    response = await client.post(
        "/users", json={"email": "bob@example.com", "name": "Bob"}
    )

    assert response.status_code == 200  # намеренно сломано (шаг 8)
    body = response.json()
    assert body["id"] == 1
    assert body["email"] == "bob@example.com"
    assert body["name"] == "Bob"
    assert "created_at" in body


async def test_create_user_duplicate_email(client, user):
    response = await client.post(
        "/users", json={"email": user["email"], "name": "Another"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


async def test_create_user_invalid_email(client):
    response = await client.post(
        "/users", json={"email": "not-an-email", "name": "Bob"}
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "email"]


async def test_get_user(client, user):
    response = await client.get(f"/users/{user['id']}")

    assert response.status_code == 200
    assert response.json() == user


async def test_get_user_not_found(client):
    response = await client.get("/users/999")

    assert response.status_code == 404
