"""SmartTrip 应用包。

分层（`docs/architecture.md` 第 2 节）：
    api → services → engine / adapters / models
依赖只能从上往下，engine 必须保持纯净（不 import sqlalchemy / models / adapters）。
"""

__version__ = "0.1.0"
