"""仓库根 conftest：保证 experiments 包在 pytest 下可导入。

tests/conftest.py 已把仓库根加入 sys.path，这里再兜一层，
使得直接运行 ``pytest experiments/...`` 或 IDE 导入用例时同样可用。
"""
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
