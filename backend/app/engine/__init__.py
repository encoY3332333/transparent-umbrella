"""排程引擎包。

**纯净层**：只允许依赖标准库与本包内的 dataclass。
禁止 import `app.models` / `app.adapters` / `sqlalchemy`——
这样排程算法可以脱离数据库与网络单测（architecture.md 分层约束第 3 条）。

具体实现（Selector / Scorer / Packer / Feasibility / BudgetIterator）由 Issue #4 落地。
"""
