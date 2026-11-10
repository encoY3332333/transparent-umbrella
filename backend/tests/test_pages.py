"""首页与静态资源的冒烟测试。

重点验证「断网可用」：页面里不得出现任何 http(s) 的 CDN 链接。
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_index_renders_html(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "SmartTrip" in body
    assert "工程骨架" in body


def test_index_references_local_assets_only(client: TestClient) -> None:
    body = client.get("/").text

    assert "/static/css/app.css" in body
    assert "/static/vendor/htmx.min.js" in body
    assert "/static/vendor/alpine.min.js" in body
    assert "https://unpkg.com" not in body
    assert "cdn.jsdelivr.net" not in body


def test_static_css_served(client: TestClient) -> None:
    response = client.get("/static/css/app.css")

    assert response.status_code == 200
    assert "--brand" in response.text


def test_static_vendor_bundles_served(client: TestClient) -> None:
    for path in ("/static/vendor/htmx.min.js", "/static/vendor/alpine.min.js"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert len(response.content) > 10_000, path


def test_unknown_path_returns_unified_error_body(client: TestClient) -> None:
    response = client.get("/no-such-page")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "NOT_FOUND"
    assert body["message"]
    assert body["traceId"]
