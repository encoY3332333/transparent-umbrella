"""UC-05 行程调整页骨架测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_adjust_page_renders_mock_itinerary(client: TestClient) -> None:
    response = client.get("/itineraries/1/adjust")

    assert response.status_code == 200
    assert "行程调整" in response.text
    assert 'data-day="1"' in response.text
    assert 'data-activity-id="101"' in response.text
    assert 'data-activity-id="201"' in response.text
    assert "陕西历史博物馆" in response.text
    assert "秦始皇帝陵博物院（兵马俑）" in response.text


def test_adjust_page_marks_locked_activity(client: TestClient) -> None:
    body = client.get("/itineraries/1/adjust").text

    assert 'data-activity-id="101"' in body
    assert 'data-locked="true"' in body
    assert "锁定" in body


def test_adjust_page_shows_validation_and_budget(client: TestClient) -> None:
    body = client.get("/itineraries/1/adjust").text

    assert 'data-status="ok"' in body
    assert "当前方案无冲突" in body
    assert "¥6000" in body
    assert "¥5680" in body
    assert "¥320" in body
