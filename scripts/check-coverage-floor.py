#!/usr/bin/env python3
"""核心模块覆盖率门槛（Issue #14）。

为什么不用 coverage.py 自带的 `fail_under`：
coverage.py 只支持**全局**阈值，不能对单个目录设线。Issue 要求
`engine/` 与 `services/` ≥ 60%、整体 ≥ 40%，只能自己解析 coverage.xml。

约定（Issue #14 技术备注）：CI 命令里的 `--cov-fail-under=40` 管总量，
本脚本管核心模块的 60% 两条线，两者职责不同、不冲突。

用法：`python scripts/check-coverage-floor.py backend/coverage.xml`
（在 pytest `--cov-report=xml` 之后运行）
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# 目录前缀 -> 最低行覆盖率。
# `--cov=app` 时 coverage 把 `app` 当作 source 根，XML 里 filename 形如
# `engine/packer.py`（**不带** `app/` 前缀）。这一点容易看反，写成
# `app/engine/` 会导致永远匹配不到、门禁静默失效。
FLOORS: dict[str, float] = {
    "engine/": 60.0,
    "services/": 60.0,
}
GLOBAL_FLOOR = 40.0


def main(argv: list[str]) -> int:
    if not argv:
        print("用法: check-coverage-floor.py <coverage.xml>")
        return 2
    xml_path = Path(argv[0])
    if not xml_path.exists():
        # 这条提示只针对「测试提前失败、没产出 xml」这一种情况；
        # 「忘了加 --cov-report=xml」由 ci.yml 的步骤本身保证，不在这里重复提示。
        print(f"::error::pytest 未产出 {xml_path}，请先检查上一步 Test with coverage 的退出码")
        return 2

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # <class filename="app/engine/packer.py" line-rate="0.95" ...>
    rates: dict[str, float] = {}
    for cls in root.iter("class"):
        name = (cls.get("filename") or "").replace("\\", "/")
        try:
            rates[name] = float(cls.get("line-rate") or 0.0) * 100.0
        except ValueError:
            rates[name] = 0.0

    failures: list[str] = []

    for prefix, floor in FLOORS.items():
        matched = {n: r for n, r in rates.items() if n.replace("\\", "/").startswith(prefix)}
        if not matched:
            # 目录还没落地时（如 services/ 在 Issue #4/#7 之前）不卡，只提醒。
            # engine/ 在 #6 已存在，若这条 notice 指向 engine/，多半是 coverage
            # 的 source 根或前缀写错了（写 `app/engine/` 就会永远匹配不到），
            # 所以把实际看到的前缀一起打出来便于核对。
            seen = sorted({n.split("/")[0] for n in rates if "/" in n})
            print(
                f"::notice::{prefix} 尚无被测文件，跳过 {floor:.0f}% 门槛"
                f"（coverage 里的顶层目录：{', '.join(seen) or '无'}）"
            )
            continue
        worst_name = min(matched, key=matched.get)  # type: ignore[arg-type]
        worst = matched[worst_name]
        status = "OK" if worst >= floor else "FAIL"
        print(f"{status} {prefix} 最低 {worst:.1f}%（文件 {worst_name}，门槛 {floor:.0f}%）")
        if worst < floor:
            failures.append(f"{prefix} 核心模块覆盖率 {worst:.1f}% < {floor:.0f}%（最低文件：{worst_name}）")

    global_rate = float(root.get("line-rate") or 0.0) * 100.0
    status = "OK" if global_rate >= GLOBAL_FLOOR else "FAIL"
    print(f"{status} 整体覆盖率 {global_rate:.1f}%（门槛 {GLOBAL_FLOOR:.0f}%）")
    if global_rate < GLOBAL_FLOOR:
        failures.append(f"整体覆盖率 {global_rate:.1f}% < {GLOBAL_FLOOR:.0f}%")

    if failures:
        print()
        for f in failures:
            print(f"::error::{f}")
        return 1
    print("覆盖率门槛全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
