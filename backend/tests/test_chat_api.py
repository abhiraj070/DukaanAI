"""AI Chat ownership, authentication, and mode authorization checks."""

from app.core.security import create_access_token, hash_password
from app.models.identity import User


def headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user_id})}"}


def test_conversation_crud_is_private_to_authenticated_owner(client, tenants: dict):
    user_a = tenants["tenant_a"]["context"].user_id
    user_b = tenants["tenant_b"]["context"].user_id
    created = client.post(
        "/api/v1/chat/conversations", json={"mode": "general"}, headers=headers(user_a)
    )
    assert created.status_code == 200
    conversation_id = created.json()["id"]

    own_list = client.get("/api/v1/chat/conversations", headers=headers(user_a))
    assert [item["id"] for item in own_list.json()] == [conversation_id]
    foreign_read = client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=headers(user_b)
    )
    assert foreign_read.status_code == 404

    unauthenticated = client.get("/api/v1/chat/conversations")
    assert unauthenticated.status_code == 401


def test_business_context_requires_membership_before_provider_call(
    client, db_session, tenants: dict
):
    user_id = tenants["tenant_a"]["context"].user_id
    created = client.post(
        "/api/v1/chat/conversations", json={"mode": "general"}, headers=headers(user_id)
    )
    conversation_id = created.json()["id"]
    outsider = User(
        email="chat-outsider@example.test",
        full_name="Chat Outsider",
        hashed_password=hash_password("password"),
    )
    db_session.add(outsider)
    db_session.commit()
    response = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/messages",
        json={"content": "Show my stock", "mode": "business"},
        headers=headers(outsider.id),
    )
    assert response.status_code == 403
