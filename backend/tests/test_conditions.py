"""UC-02 出行条件的接口与页面测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

VALID_PAYLOAD = {
    "originCity": "杭州",
    "destCity": "西安",
    "startDate": "2026-12-01",
    "endDate": "2026-12-04",
    "budget": 6000,
    "partySize": 2,
    "partyType": "COUPLE",
    "preferenceTags": ["人文历史", "美食"],
    "mustVisit": [205],
    "avoidPOI": [310],
}


def _post_valid(client: TestClient) -> dict:
    response = client.post("/api/conditions/validate", json=VALID_PAYLOAD)
    assert response.status_code == 200, response.text
    return response.json()


def test_validate_accepts_valid_condition(client: TestClient) -> None:
    body = _post_valid(client)

    assert body["code"] == "OK"
    assert body["data"]["valid"] is True
    assert body["data"]["days"] == 4
    assert body["data"]["resolved"]["origin"]["city"] == "杭州"
    assert body["data"]["resolved"]["dest"]["city"] == "西安"
    assert body["data"]["budgetBreakdownHint"]["perDay"] == 1500.0
    assert body["data"]["budgetBreakdownHint"]["perPersonPerDay"] == 750.0


def test_validate_rejects_reversed_dates(client: TestClient) -> None:
    payload = {**VALID_PAYLOAD, "startDate": "2026-12-04", "endDate": "2026-12-01"}
    response = client.post("/api/conditions/validate", json=payload)

    assert response.status_code == 400
    assert response.json()["code"] == "CONDITION_INVALID_DATE_RANGE"


def test_validate_rejects_duration_over_15_days(client: TestClient) -> None:
    payload = {**VALID_PAYLOAD, "endDate": "2026-12-16"}
    response = client.post("/api/conditions/validate", json=payload)

    assert response.status_code == 400
    assert response.json()["code"] == "CONDITION_DURATION_OUT_OF_RANGE"


def test_validate_rejects_budget_below_500(client: TestClient) -> None:
    payload = {**VALID_PAYLOAD, "budget": 100}
    response = client.post("/api/conditions/validate", json=payload)

    assert response.status_code == 400
    assert response.json()["code"] == "CONDITION_BUDGET_OUT_OF_RANGE"


def test_validate_rejects_more_than_six_tags(client: TestClient) -> None:
    payload = {**VALID_PAYLOAD, "preferenceTags": ["a", "b", "c", "d", "e", "f", "g"]}
    response = client.post("/api/conditions/validate", json=payload)

    assert response.status_code == 400
    assert response.json()["code"] == "CONDITION_TOO_MANY_TAGS"


def test_validate_rejects_must_visit_overlap(client: TestClient) -> None:
    payload = {**VALID_PAYLOAD, "mustVisit": [205], "avoidPOI": [205]}
    response = client.post("/api/conditions/validate", json=payload)

    assert response.status_code == 400
    assert response.json()["code"] == "CONDITION_MUST_VISIT_CONFLICT"


def test_validate_rejects_unknown_city(client: TestClient) -> None:
    payload = {**VALID_PAYLOAD, "destCity": "火星"}
    response = client.post("/api/conditions/validate", json=payload)

    assert response.status_code == 400
    assert response.json()["code"] == "CONDITION_CITY_UNRESOLVED"


def test_condition_page_renders_form(client: TestClient) -> None:
    response = client.get("/conditions/new")

    assert response.status_code == 200
    assert "出行条件" in response.text
    assert 'name="originCity"' in response.text
    assert "校验条件" in response.text


def test_condition_page_shows_validation_result(client: TestClient) -> None:
    data = {
        "originCity": "杭州",
        "destCity": "西安",
        "startDate": "2026-12-01",
        "endDate": "2026-12-04",
        "budget": "6000",
        "partySize": "2",
        "partyType": "COUPLE",
        "mustVisit": "205",
        "avoidPOI": "310",
        "preferenceTags": ["人文历史", "美食"],
    }
    response = client.post("/conditions/validate", data=data)

    assert response.status_code == 200
    assert "条件可用：4 天行程" in response.text
    assert "杭州" in response.text
    assert "西安" in response.text


def test_condition_page_shows_error_for_bad_date(client: TestClient) -> None:
    data = {
        "originCity": "杭州",
        "destCity": "西安",
        "startDate": "2026-12-04",
        "endDate": "2026-12-01",
        "budget": "6000",
        "partySize": "2",
        "partyType": "COUPLE",
    }
    response = client.post("/conditions/validate", data=data)

    assert response.status_code == 200
    assert "条件没有通过校验" in response.text
    assert "结束日期不能早于开始日期" in response.text
