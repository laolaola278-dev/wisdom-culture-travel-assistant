import pytest
import subprocess
import os
import sys

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend"
)

# Windows 下 npx 是 npx.cmd，subprocess 需显式指定
NPX = "npx.cmd" if sys.platform == "win32" else "npx"


@pytest.mark.slow
def test_vite_build():
    result = subprocess.run(
        [NPX, "vite", "build"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"Vite build failed:\n{result.stderr}"


def test_build_output_exists():
    dist_dir = os.path.join(FRONTEND_DIR, "dist")
    index_html = os.path.join(dist_dir, "index.html")
    assert os.path.exists(index_html), f"构建产物缺失: {index_html}"
    with open(index_html, "r", encoding="utf-8") as f:
        content = f.read()
    assert "白云" in content


@pytest.mark.slow
def test_vue_typecheck():
    result = subprocess.run(
        [NPX, "vue-tsc", "--noEmit"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"vue-tsc 类型检查失败:\n{result.stderr}"
