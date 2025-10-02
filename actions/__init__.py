# my_package/__init__.py
import os
import importlib

# 获取当前目录下所有 .py 文件（排除 __init__.py）
module_files = [
    f[:-3] for f in os.listdir(os.path.dirname(__file__))
    if f.endswith('.py') and f != '__init__.py'
]

# 导入所有模块
for module_name in module_files:
    # 动态导入模块
    importlib.import_module(f'.{module_name}', package=__name__)