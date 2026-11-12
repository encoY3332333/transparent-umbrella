"""HTML 页面路由（服务端渲染入口）。

页面与 JSON 接口**共用同一个进程**：`/` 返回 HTML，`/api/**` 返回 JSON。
HTMX 的局部刷新也走 `/api/**` 或本模块的片段路由，前端不再维护第二套构建链。
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["pages"], include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """首页：展示工程骨架状态与两个运行时检查入口。"""
    templates: Jinja2Templates = request.app.state.templates
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": settings.app_name,
            "app_env": settings.app_env,
            "app_version": settings.app_version,
            "offline": True,
        },
    )


@router.get("/itineraries/{itinerary_id}/adjust", response_class=HTMLResponse)
def adjustment_page(request: Request, itinerary_id: int) -> HTMLResponse:
    """行程调整页骨架（UC-05）。

    当前使用 mock 行程，先把页面结构与交互占位跑通；
    等 #8 的行程详情接口落地后，把 mock 替换为 service 查询即可。
    """
    templates: Jinja2Templates = request.app.state.templates
    settings = request.app.state.settings
    mock_itinerary = {
        "id": itinerary_id,
        "title": "杭州 → 西安 4 日行程",
        "budget": 6000,
        "estimated_cost": 5680,
        "days": [
            {
                "day": 1,
                "date": "2026-12-01",
                "activities": [
                    {
                        "id": 101,
                        "time": "09:00",
                        "name": "陕西历史博物馆",
                        "category": "人文历史",
                        "cost": 0,
                        "locked": True,
                    },
                    {
                        "id": 102,
                        "time": "14:00",
                        "name": "大雁塔",
                        "category": "人文历史",
                        "cost": 50,
                        "locked": False,
                    },
                ],
            },
            {
                "day": 2,
                "date": "2026-12-02",
                "activities": [
                    {
                        "id": 201,
                        "time": "09:00",
                        "name": "秦始皇帝陵博物院（兵马俑）",
                        "category": "人文历史",
                        "cost": 120,
                        "locked": False,
                    },
                    {
                        "id": 202,
                        "time": "15:30",
                        "name": "回民街",
                        "category": "美食",
                        "cost": 80,
                        "locked": False,
                    },
                ],
            },
            {
                "day": 3,
                "date": "2026-12-03",
                "activities": [
                    {
                        "id": 301,
                        "time": "10:00",
                        "name": "西安城墙（永宁门）",
                        "category": "人文历史",
                        "cost": 54,
                        "locked": False,
                    }
                ],
            },
        ],
    }
    return templates.TemplateResponse(
        request,
        "itinerary/adjust.html",
        {
            "app_name": settings.app_name,
            "app_env": settings.app_env,
            "app_version": settings.app_version,
            "itinerary": mock_itinerary,
        },
    )
