# -*- coding: utf-8 -*-
"""把 docs/diagrams/*.puml 渲染为 docs/diagrams/png/*.png。

输出文件名由 MAP 决定，**必须**与 SRS 正文引用的一致，
否则 docx 里的图会变成红叉。

依赖：
  - JDK 17+（java 在 PATH 上，或设置了 JAVA_HOME）
  - plantuml.jar（默认取环境变量 PLANTUML_JAR，否则 ./plantuml.jar）

用法：
  python scripts/render-diagrams.py
  PLANTUML_JAR=/opt/plantuml.jar python scripts/render-diagrams.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIA = os.path.join(ROOT, "docs", "diagrams")
OUT = os.path.join(DIA, "png")

# puml 源码 → 成品图文件名（与 SRS 正文引用一致，勿随意改）
MAP = {
    "usecase.puml": "use-case.png",
    "seq-uc01-login.puml": "seq-uc01.png",
    "seq-uc02-condition.puml": "seq-uc02.png",
    "seq-uc03-generate.puml": "seq-uc03.png",
    "seq-uc04-view.puml": "seq-uc04.png",
    "seq-uc05-adjust.puml": "seq-uc05.png",
    "seq-uc06-share.puml": "seq-uc06.png",
    "seq-uc07-feedback.puml": "seq-uc07.png",
    "seq-uc08-poi-admin.puml": "seq-uc08.png",
    "seq-uc09-strategy.puml": "seq-uc09.png",
    "class-analysis.puml": "class-analysis.png",
    "state-itinerary.puml": "state-itinerary.png",
    "state-poi.puml": "state-poi.png",
    "ui-flow.puml": "ui-flow.png",
}


def find_java():
    jar_java = os.path.join(os.environ.get("JAVA_HOME", ""), "bin",
                            "java.exe" if os.name == "nt" else "java")
    if os.environ.get("JAVA_HOME") and os.path.exists(jar_java):
        return jar_java
    found = shutil.which("java")
    if found:
        return found
    sys.exit("找不到 java。请安装 JDK 17+，或设置 JAVA_HOME。")


def main():
    jar = os.environ.get("PLANTUML_JAR") or os.path.join(ROOT, "plantuml.jar")
    if not os.path.exists(jar):
        sys.exit("找不到 plantuml.jar。设置环境变量 PLANTUML_JAR，或把它放到仓库根目录。")

    java = find_java()
    os.makedirs(OUT, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        work = []
        for src, png in MAP.items():
            sp = os.path.join(DIA, src)
            if not os.path.exists(sp):
                print("跳过（源文件缺失）：", src)
                continue
            stem = os.path.splitext(png)[0]
            # PlantUML 的输出文件名取自 @startuml 后的标识符，必须同步改写
            lines = open(sp, encoding="utf-8").read().split("\n")
            for i, ln in enumerate(lines):
                if ln.strip().startswith("@startuml"):
                    lines[i] = "@startuml " + stem
                    break
            dp = os.path.join(tmp, stem + ".puml")
            open(dp, "w", encoding="utf-8").write("\n".join(lines))
            work.append(dp)

        if not work:
            sys.exit("没有可渲染的源文件。")

        cmd = [
            java,
            "-Dfile.encoding=UTF-8",
            # 默认上限 4096px，超宽的顺序图会被静默裁掉右侧
            "-DPLANTUML_LIMIT_SIZE=16384",
            "-jar", jar,
            "-tpng", "-charset", "UTF-8", "-nometadata", "-Sdpi=200",
            "-o", OUT,
        ] + work
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr)
            sys.exit("渲染失败，退出码 %d" % r.returncode)

    for png in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, png)
        print("  %-24s %5d KB" % (png, os.path.getsize(p) // 1024))
    print("\n完成，输出目录：", OUT)


if __name__ == "__main__":
    main()
