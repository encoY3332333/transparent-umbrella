"""HTML 页面路由（服务端渲染入口）。

页面与 JSON 接口**共用同一个进程**：`/` 返回 HTML，`/api/**` 返回 JSON。
HTMX 的局部刷新也走 `/api/**` 或本模块的片段路由，前端不再维护第二套构建链。
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.deps import DbDep
from app.services.strategy_service import StrategyService

router = APIRouter(tags=["pages"], include_in_schema=False)

# 五项权重的展示名。键必须与 `models.strategy.WEIGHT_KEYS` 一致——
# 页面、接口、引擎三处用同一套键，靠这一个字典给中文名。
WEIGHT_LABELS: dict[str, str] = {
    "preference": "偏好匹配 w_pref",
    "weather": "天气适配 w_weather",
    "crowd": "拥挤度 w_crowd",
    "travel": "通勤代价 w_travel",
    "cost": "费用 w_cost",
}

THRESHOLD_LABELS: dict[str, tuple[str, str]] = {
    "dailyHours": ("单日游玩时长上限", "小时"),
    "maxWalkMinutes": ("连续步行上限", "分钟"),
    "longTransferMinutes": ("长途转移阈值", "分钟"),
    "crowdAvoidThreshold": ("拥挤避峰线", "拥挤度"),
    "maxIteration": ("降本迭代上限", "次"),
}


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


@router.get("/admin/strategy", response_class=HTMLResponse)
def admin_strategy(request: Request, session: DbDep) -> HTMLResponse:
    """策略参数配置页（UC-09 / SRS 第 5 章 S8）。

    页面首屏由服务端渲染（当前参数 + 版本列表），交互部分交给 Alpine：
    滑块实时求和、一键归一化、发布时的二次确认。**不做整页刷新提交**——
    权重和不为 1 时要保留用户已经调好的滑块位置，整页刷新会把它们重置回库里的值。
    """
    settings = request.app.state.settings
    templates: Jinja2Templates = request.app.state.templates
    service = StrategyService(session)
    current = service.current()
    return templates.TemplateResponse(
        request,
        "admin/strategy.html",
        {
            "app_name": settings.app_name,
            "app_env": settings.app_env,
            "app_version": settings.app_version,
            "current": current,
            "versions": service.list_versions(),
            "weights": current.weights,
            "thresholds": current.thresholds,
            "holiday_factors": current.holiday_factors,
            "disabled_fallbacks": list(current.disabled_fallbacks),
            "weight_labels": WEIGHT_LABELS,
            "threshold_labels": THRESHOLD_LABELS,
        },
    )
