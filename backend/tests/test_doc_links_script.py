"""`scripts/check-doc-links.py` 的回归测试（Issue #14）。

脚本文件名带连字符，不能 `import`，用 importlib 按路径加载。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-doc-links.py"


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_doc_links", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_link_escaping_repo_is_reported_not_crashing(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """指向仓库外的链接应被报告为死链，而不是让脚本抛 ValueError。

    回归点：`resolved.relative_to(REPO_ROOT)` 在目标越出仓库时抛 ValueError，
    原实现没有兜住，整个脚本会崩——而它的职责是报告坏链接，不是崩掉。
    """
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    monkeypatch.setattr(mod, "REPO_ROOT", repo)

    md = repo / "docs" / "page.md"
    md.write_text("[escape](../../outside/target.md)\n", encoding="utf-8")

    broken = mod.broken_links(md)

    assert len(broken) == 1
    assert "../../outside/target.md" in broken[0]


def test_existing_relative_link_is_not_broken(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    monkeypatch.setattr(mod, "REPO_ROOT", repo)

    target = repo / "docs" / "other.md"
    target.write_text("# ok\n", encoding="utf-8")
    md = repo / "docs" / "page.md"
    md.write_text("[ok](./other.md#section)\n", encoding="utf-8")

    assert mod.broken_links(md) == []


def test_external_and_anchor_links_are_skipped(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    monkeypatch.setattr(mod, "REPO_ROOT", repo)

    md = repo / "docs" / "page.md"
    md.write_text(
        "[a](https://example.com/x.md)\n[b](mailto:x@y.com)\n[c](#local-anchor)\n",
        encoding="utf-8",
    )

    assert mod.broken_links(md) == []
