#!/usr/bin/env python3
"""Jinja2 模板检查：编译全部模板，并校验静态资源引用是否存在。

前端改为服务端渲染后，没有 `npm run build` 来暴露模板里的低级错误。
模板写错一个 `{%` 或引用了不存在的静态文件，只会在运行时报 500。
这个脚本把这类错误前移到 CI。

用法：
    python scripts/check-templates.py [--templates DIR] [--static DIR]

退出码：
    0 全部通过
    1 存在语法错误或缺失的静态资源
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

DEFAULT_TEMPLATES = Path("backend/app/templates")
DEFAULT_STATIC = Path("backend/app/static")

# 模板中引用静态资源的写法，需与 base.html 里的约定保持一致
STATIC_REF = re.compile(r"""\{\{\s*url_for\(\s*['"]static['"]\s*,\s*path\s*=\s*['"]([^'"]+)['"]""")
LITERAL_STATIC = re.compile(r"""<(?:link|script|img)[^>]+(?:href|src)=["']/static/([^"'?#]+)""")


def find_templates(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.suffix in {".html", ".jinja", ".jinja2"})


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 Jinja2 模板语法与静态资源引用")
    parser.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES)
    parser.add_argument("--static", type=Path, default=DEFAULT_STATIC)
    args = parser.parse_args()

    files = find_templates(args.templates)
    if not files:
        print(f"[skip] 未在 {args.templates} 找到模板文件")
        return 0

    env = Environment(loader=FileSystemLoader(str(args.templates)))
    errors: list[str] = []

    for path in files:
        rel = path.relative_to(args.templates).as_posix()
        source = path.read_text(encoding="utf-8")

        # 1) 语法编译
        try:
            env.from_string(source)
        except TemplateSyntaxError as exc:
            errors.append(f"{rel}:{exc.lineno} 语法错误 — {exc.message}")
            continue

        # 2) 静态资源引用
        for ref in STATIC_REF.findall(source) + LITERAL_STATIC.findall(source):
            if ref.startswith(("http://", "https://", "//", "data:")):
                continue
            if not (args.static / ref).exists():
                errors.append(f"{rel}: 引用不存在的静态资源 static/{ref}")

    # 3) 模板继承关系完整性：{% extends "x.html" %} 的目标必须存在
    for path in files:
        rel = path.relative_to(args.templates).as_posix()
        for target in re.findall(r"""\{%-?\s*extends\s+["']([^"']+)["']""", path.read_text(encoding="utf-8")):
            if not (args.templates / target).exists():
                errors.append(f"{rel}: extends 目标不存在 — {target}")

    if errors:
        print(f"发现 {len(errors)} 个问题：\n", file=sys.stderr)
        for err in errors:
            print(f"  ✗ {err}", file=sys.stderr)
        return 1

    print(f"✓ {len(files)} 个模板全部编译通过，静态资源引用有效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
