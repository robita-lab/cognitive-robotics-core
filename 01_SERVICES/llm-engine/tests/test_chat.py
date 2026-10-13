async def test_chat_non_streaming(client):
    resp = await client.post(
        "/v1/chat",
        json={"conversation_id": "c1", "user_text": "Hola"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation_id"] == "c1"
    assert body["reply"] == "hola, soy UDITO"

    resp = await client.get("/v1/conversations/c1")
    assert resp.status_code == 200
    turns = resp.json()["turns"]
    assert [t["role"] for t in turns] == ["user", "assistant"]
    assert turns[0]["content"] == "Hola"


async def test_chat_with_recent_context(client):
    resp = await client.post(
        "/v1/chat",
        json={
            "conversation_id": "c2",
            "user_text": "¿Y tú?",
            "recent_context": [
                {"role": "user", "content": "Hola"},
                {"role": "assistant", "content": "Hola, ¿qué tal?"},
            ],
        },
    )
    assert resp.status_code == 200

    resp = await client.get("/v1/conversations/c2")
    turns = resp.json()["turns"]
    assert len(turns) == 4
    assert turns[0]["content"] == "Hola"
    assert turns[-1]["content"] == "hola, soy UDITO"


async def test_chat_stream(client):
    async with client.stream(
        "POST",
        "/v1/chat/stream",
        json={"conversation_id": "c3", "user_text": "Hola"},
    ) as resp:
        assert resp.status_code == 200
        body = await resp.aread()
    text = body.decode()
    assert "event: token" in text
    assert "event: done" in text


async def test_reset_conversation(client):
    await client.post("/v1/chat", json={"conversation_id": "c4", "user_text": "Hola"})
    resp = await client.delete("/v1/conversations/c4")
    assert resp.status_code == 200
    assert resp.json()["reset"] is True

    resp = await client.get("/v1/conversations/c4")
    assert resp.json()["turns"] == []
