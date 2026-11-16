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


@router.get("/itineraries/new", response_class=HTMLResponse)
def new_itinerary(request: Request) -> HTMLResponse:
    """生成行程页（UC-03 第一步：填条件）。

    表单提交走 `hx-post` 到片段接口，本页只负责渲染表单与加载态；
    结果替换进 `#plan-result`，不整页刷新——用户填的条件不会被冲掉。
    """
    settings = request.app.state.settings
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "itineraries/new.html",
        {
            "app_name": settings.app_name,
            "app_env": settings.app_env,
            "app_version": settings.app_version,
        },
    )
