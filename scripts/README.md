# scripts/

构建、发布与演示脚本。所有脚本都以**仓库根**（本目录的父目录）为 ROOT 解析路径，
因此从任何工作目录双击 / 调用都能正确找到 `.venv`、`data/`、`tools/`。

## 一览

| 脚本 | 用途 | 用法 |
|---|---|---|
| `build_exe.py` | PyInstaller 打包为 `dist/IntelNexus/`（EXE 分发） | `python scripts/build_exe.py [--clean] [--spec-only]` |
| `make_release.bat` | 打干净的**源码分发** zip（排除 `.env`/`data/`/`temp/`/`tools/`/`.venv`/`.git`，并扫描密钥泄露） | 双击 |
| `check_demo.bat` | 演示前链路自检的一键入口 | 双击 |
| `preflight_demo.py` | 自检逻辑本体：Clash 端口、Tor SOCKS、出口身份、Ahmia、端到端暗网搜索 | `.venv\Scripts\python.exe scripts\preflight_demo.py [--full]` |
| `start_tor.bat` | 启动 Tor 并等待引导完成（一键入口） | 双击 |
| `start_tor.py` | 启动逻辑本体（`DETACHED_PROCESS` 脱离控制台） | `.venv\Scripts\python.exe scripts\start_tor.py` |

## 路径约定

| 脚本 | 约定 | 移动时的同步点 |
|---|---|---|
| `build_exe.py` | `ROOT = Path(__file__).resolve().parent.parent` | 所有 `ROOT / "xxx"` 派生路径自动跟随 |
| `preflight_demo.py` | 把仓库根插入 `sys.path` | `--full` 分支的 `from intelnexus...` 依赖它 |
| `start_tor.py` | `ROOT = Path(__file__).resolve().parent.parent` | `data/tor_runtime/`、`tools/tor/` |
| `make_release.bat` | `PROJ_ROOT=%~dp0..` | robocopy 源与 `dist/` 输出 |
| `check_demo.bat` `start_tor.bat` | `cd /d "%~dp0.."` 后用 `%~dp0xxx.py` 调用 | `.venv` 相对根；脚本本体在 scripts/ 下 |

## CI

`.github/workflows/build-exe.yml` 调用 `python scripts/build_exe.py`，路径必须与上表一致。
