"""HTML 页面路由（服务端渲染入口）。

页面与 JSON 接口**共用同一个进程**：`/` 返回 HTML，`/api/**` 返回 JSON。
HTMX 的局部刷新也走 `/api/**` 或本模块的片段路由，前端不再维护第二套构建链。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.core.errors import BusinessError
from app.schemas.condition import ConditionValidationOut, TravelConditionIn
from app.services.condition_service import validate_condition

router = APIRouter(tags=["pages"], include_in_schema=False)


def _context(request: Request, **extra: Any) -> dict[str, Any]:
    """所有页面都要带上的基础模板变量。"""
    settings = request.app.state.settings
    context: dict[str, Any] = {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "app_version": settings.app_version,
    }
    context.update(extra)
    return context


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """首页：展示工程骨架状态与两个运行时检查入口。"""
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "index.html",
        _context(request, offline=True),
    )


def _parse_poi_ids(raw: str, field: str) -> list[int]:
    """把逗号分隔的 POI ID 转成整数列表；空字符串视为空列表。"""
    if not raw.strip():
        return []
    try:
        return [int(part.strip()) for part in raw.split(",") if part.strip()]
    except ValueError as exc:
        raise ValueError(f"{field} 必须是逗号分隔的数字") from exc


@router.get("/conditions/new", response_class=HTMLResponse)
def condition_form(request: Request) -> HTMLResponse:
    """条件录入页：默认给一组可演示的西安 4 日条件。"""
    templates: Jinja2Templates = request.app.state.templates
    start = date.today() + timedelta(days=7)
    end = start + timedelta(days=3)
    form = {
        "originCity": "杭州",
        "destCity": "西安",
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "budget": "6000",
        "partySize": "2",
        "partyType": "COUPLE",
        "preferenceTags": ["人文历史", "美食"],
        "mustVisit": "205",
        "avoidPOI": "",
    }
    return templates.TemplateResponse(
        request,
        "conditions/form.html",
        _context(request, form=form, result=None, errors=[]),
    )


@router.post("/conditions/validate", response_class=HTMLResponse)
async def condition_validate(request: Request) -> HTMLResponse:
    """表单版校验：与 JSON 接口共用同一个 service。"""
    templates: Jinja2Templates = request.app.state.templates
    raw_form = await request.form()
    form: dict[str, Any] = {key: value for key, value in raw_form.items()}
    form["preferenceTags"] = raw_form.getlist("preferenceTags")

    errors: list[str] = []
    result: ConditionValidationOut | None = None
    try:
        payload = TravelConditionIn(
            originCity=str(raw_form.get("originCity", "")).strip(),
            destCity=str(raw_form.get("destCity", "")).strip(),
            startDate=str(raw_form.get("startDate", "")),
            endDate=str(raw_form.get("endDate", "")),
            budget=float(str(raw_form.get("budget", "0"))),
            partySize=int(str(raw_form.get("partySize", "0"))),
            partyType=str(raw_form.get("partyType", "SOLO")),
            preferenceTags=form["preferenceTags"],
            mustVisit=_parse_poi_ids(str(raw_form.get("mustVisit", "")), "mustVisit"),
            avoidPOI=_parse_poi_ids(str(raw_form.get("avoidPOI", "")), "avoidPOI"),
        )
        result = validate_condition(payload)
    except ValidationError as exc:
        for item in exc.errors():
            field = ".".join(str(part) for part in item.get("loc", ()) if part != "body")
            errors.append(f"{field}: {item.get('msg', '输入不合法')}")
    except ValueError as exc:
        errors.append(str(exc))
    except BusinessError as exc:
        errors.append(exc.message or "条件校验失败")
        errors.extend(f"{d.field}: {d.reason}" for d in exc.details)

    return templates.TemplateResponse(
        request,
        "conditions/form.html",
        _context(request, form=form, result=result, errors=errors),
    )
