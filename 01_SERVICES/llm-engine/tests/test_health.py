async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["tier"] in {"server", "local"}


async def test_readyz(client):
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["llm"] is True
    assert body["memory"] is True


async def test_models(client):
    resp = await client.get("/v1/models")
    assert resp.status_code == 200
    body = resp.json()
    assert "default" in body
    assert "fake-model" in body["available"]
