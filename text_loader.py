import os
import random
import glob
import re
from typing import List, Tuple

# 模拟WAS相关基础组件（避免外部依赖）
class MockWASDatabase:
    def __init__(self, path):
        self.path = path

class cstr:
    def __init__(self, msg):
        self.msg = msg
    @property
    def error(self):
        return self
    @property
    def warning(self):
        return self
    def print(self):
        print(self.msg)

WAS_HISTORY_DATABASE = "mock_history.db"
WASDatabase = MockWASDatabase
TEXT_TYPE = "STRING"


def natural_key(path: str):
    # 与资源管理器一致的自然排序：数字段按数值比较（1.txt < 2.txt < 10.txt）
    return ([int(p) if p.isdigit() else p for p in re.split(r'(\d+)', path.casefold())], path)

class Moyou_Text_Batch_Loader:
    def __init__(self):
        self.HDB = WASDatabase(WAS_HISTORY_DATABASE)
        self.batch_loaders = {}  # 用label区分不同批次的状态

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (["single_text", "incremental_text", "random"],),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "index": ("INT", {"default": 0, "min": 0, "max": 150000, "step": 1}),
                "label": ("STRING", {"default": 'Batch 001', "multiline": False}),
                "path": ("STRING", {"default": '', "multiline": False}),
                "pattern": ("STRING", {"default": '*.txt', "multiline": False}),
                "encoding": (["utf-8", "gbk", "utf-16"],),
            },
            "optional": {
                "filename_text_extension": (["true", "false"],),
            }
        }

    RETURN_TYPES = (TEXT_TYPE, "STRING", "INT", "INT")
    RETURN_NAMES = ("text_content", "filename", "current_index", "total_count")
    FUNCTION = "load_batch_texts"
    CATEGORY = "WAS Suite/IO"

    class BatchTextLoader:
        def __init__(self, path: str, label: str, pattern: str):
            self.path = path
            self.label = label
            self.pattern = pattern
            self.current_index = 0
            self.text_paths = self._load_text_paths()

        def _load_text_paths(self) -> List[str]:
            if not os.path.exists(self.path):
                return []
            text_paths = glob.glob(os.path.join(self.path, self.pattern))
            return sorted(text_paths, key=natural_key)  # 按文件名自然排序（与资源管理器一致）

        def get_text_by_id(self, index: int, encoding: str) -> Tuple[str, str]:
            if 0 <= index < len(self.text_paths):
                file_path = self.text_paths[index]
                return self._read_text(file_path, encoding), os.path.basename(file_path)
            return None, None

        def get_next_text(self, encoding: str) -> Tuple[str, str]:
            if not self.text_paths:
                return None, None
            text, filename = self.get_text_by_id(self.current_index, encoding)
            self.current_index = (self.current_index + 1) % len(self.text_paths)
            return text, filename

        def _read_text(self, file_path: str, encoding: str) -> str:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                return f"[解码错误] 无法用{encoding}编码读取文件"
            except Exception as e:
                return f"[读取失败] {str(e)}"

    def load_batch_texts(self, path, pattern='*.txt', index=0, mode="single_text", 
                        seed=0, label='Batch 001', encoding="utf-8", filename_text_extension='false'):
        if not os.path.exists(path):
            cstr(f"路径不存在: {path}").error.print()
            return (None, None, 0, 0)

        # 初始化或获取批次加载器
        if label not in self.batch_loaders:
            self.batch_loaders[label] = self.BatchTextLoader(path, label, pattern)
        loader = self.batch_loaders[label]

        # 路径或模式变化时重置
        if loader.path != path or loader.pattern != pattern:
            loader.path = path
            loader.pattern = pattern
            loader.text_paths = loader._load_text_paths()
            loader.current_index = 0

        total_count = len(loader.text_paths)
        if total_count == 0:
            cstr(f"未找到符合模式的文本文件").warning.print()
            return (None, None, 0, 0)

        text_content = None
        filename = None
        current_index = 0

        if mode == 'single_text':
            index = max(0, min(index, total_count - 1))
            text_content, filename = loader.get_text_by_id(index, encoding)
            current_index = index
        elif mode == 'incremental_text':
            text_content, filename = loader.get_next_text(encoding)
            current_index = (loader.current_index - 1) % total_count
        else:  # random模式
            random.seed(seed)
            current_index = random.randint(0, total_count - 1)
            text_content, filename = loader.get_text_by_id(current_index, encoding)

        # 确保文件名和内容分离输出
        return (text_content, filename, current_index, total_count)
    