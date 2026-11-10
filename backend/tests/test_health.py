"""/api/health 的冒烟测试——CI 与 docker healthcheck 都依赖它。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["env"] == "test"


def test_health_sets_trace_header(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-Id": "trace-from-upstream"})

    assert response.headers["X-Trace-Id"] == "trace-from-upstream"


def test_health_generates_trace_id_when_absent(client: TestClient) -> None:
    response = client.get("/api/health")

    trace_id = response.headers["X-Trace-Id"]
    assert len(trace_id) == 12
    assert all(char in "0123456789abcdef" for char in trace_id)
