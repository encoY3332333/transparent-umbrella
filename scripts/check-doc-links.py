#!/usr/bin/env python3
"""检查 docs 与 README 里 Markdown 相对链接的目标文件是否存在（Issue #14）。

只校验**相对路径**链接（`./x.md`、`../y/z.png`、`file.md#anchor`）；
`http(s)://`、`mailto:`、纯锚点 `#section` 一律跳过——外链死没死、
锚点拼没拼对，静态检查说了不算，交给人。

CI：`Repo Conventions` job 调用；本地直接 `python scripts/check-doc-links.py` 也能跑。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOTS = [REPO_ROOT / "docs", REPO_ROOT / "README.md"]

# [text](target) —— 排除图片语法；图片用同一个链接格式，一并校验没有坏处
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def iter_markdown_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(sorted(root.rglob("*.md")))
    return files


def display_path(resolved: Path) -> str:
    """把绝对路径转成相对仓库根的展示路径；越出仓库时原样返回。

    不能直接用 `relative_to(REPO_ROOT)`：指向仓库外的链接（如 `../../../x.md`）
    会抛 ValueError 让脚本整体崩溃，而它的职责是「报告坏链接」而不是「崩掉」。
    """
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def broken_links(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    broken: list[str] = []
    for match in LINK_RE.finditer(text):
        target = match.group(1).strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        # 去掉锚点与查询串后再判断文件
        bare = target.split("#", 1)[0].split("?", 1)[0]
        if not bare:
            continue  # 纯锚点在本文件内，静态检查不判
        resolved = (path.parent / bare).resolve()
        if not resolved.exists():
            broken.append(f"{target}  （应为 {display_path(resolved)}）")
    return broken


def main() -> int:
    failures: list[str] = []
    checked = 0
    for path in iter_markdown_files():
        checked += 1
        for link in broken_links(path):
            rel = path.relative_to(REPO_ROOT)
            failures.append(f"{rel}: 死链 -> {link}")

    print(f"已扫描 {checked} 个 Markdown 文件")
    if failures:
        print(f"\n发现 {len(failures)} 个失效的相对链接：")
        for f in failures:
            print(" -", f)
        return 1
    print("所有相对链接均有效")
    return 0


if __name__ == "__main__":
    sys.exit(main())
