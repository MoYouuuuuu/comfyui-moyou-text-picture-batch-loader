import os
import glob
import json
import random
import hashlib
from typing import List

import numpy as np
import torch
from PIL import Image, ImageOps

from .text_loader import cstr, TEXT_TYPE, natural_key

# 与WAS一致的允许图像扩展名
ALLOWED_EXT = ('.jpeg', '.jpg', '.png', '.tiff', '.gif', '.bmp', '.webp')

BATCH_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'moyou_batch_state.json')


def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)


def get_sha256(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


class BatchStateDB:
    # 简易JSON键值库（模拟WAS的WASDatabase），用于跨执行保存批次进度
    def __init__(self, filepath):
        self.filepath = filepath
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            self.data = {}
            self._save()

    def insert(self, category, key, value):
        if category not in self.data:
            self.data[category] = {}
        self.data[category][key] = value
        self._save()

    def get(self, category, key):
        return self.data.get(category, {}).get(key, None)

    def _save(self):
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4)


SDB = BatchStateDB(BATCH_STATE_FILE)


class Moyou_Image_Batch_Loader:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (["single_image", "incremental_image", "random"],),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "index": ("INT", {"default": 0, "min": 0, "max": 150000, "step": 1}),
                "label": ("STRING", {"default": 'Batch 001', "multiline": False}),
                "path": ("STRING", {"default": '', "multiline": False}),
                "pattern": ("STRING", {"default": '*', "multiline": False}),
                "allow_RGBA_output": (["false", "true"],),
            },
            "optional": {
                "filename_text_extension": (["true", "false"],),
            }
        }

    RETURN_TYPES = ("IMAGE", TEXT_TYPE)
    RETURN_NAMES = ("image", "filename_text")
    FUNCTION = "load_batch_images"

    CATEGORY = "WAS Suite/IO"

    def load_batch_images(self, path, pattern='*', index=0, mode="single_image", seed=0, label='Batch 001', allow_RGBA_output='false', filename_text_extension='true'):

        allow_RGBA_output = (allow_RGBA_output == 'true')

        if not os.path.exists(path):
            cstr(f"路径不存在: {path}").error.print()
            return (None, None)

        fl = self.BatchImageLoader(path, label, pattern)

        if mode == 'single_image':
            image, filename = fl.get_image_by_id(index)
            if image is None:
                cstr(f"无效的图像编号: {index}").error.print()
                return (None, None)
        elif mode == 'incremental_image':
            image, filename = fl.get_next_image()
            if image is None:
                cstr("未找到图像，请检查路径和模式。").error.print()
                return (None, None)
        else:  # random模式
            random.seed(seed)
            newindex = int(random.random() * len(fl.image_paths))
            image, filename = fl.get_image_by_id(newindex)
            if image is None:
                cstr("未找到图像，请检查路径和模式。").error.print()
                return (None, None)

        if not allow_RGBA_output:
            image = image.convert("RGB")

        if filename_text_extension == "false":
            filename = os.path.splitext(filename)[0]

        return (pil2tensor(image), filename)

    class BatchImageLoader:
        def __init__(self, directory_path, label, pattern):
            self.WDB = SDB
            self.image_paths: List[str] = []
            self.load_images(directory_path, pattern)
            self.image_paths.sort(key=natural_key)  # 按文件名自然排序（与资源管理器一致）
            stored_directory_path = self.WDB.get('Batch Paths', label)
            stored_pattern = self.WDB.get('Batch Patterns', label)
            if stored_directory_path != directory_path or stored_pattern != pattern:
                self.index = 0
                self.WDB.insert('Batch Counters', label, 0)
                self.WDB.insert('Batch Paths', label, directory_path)
                self.WDB.insert('Batch Patterns', label, pattern)
            else:
                self.index = self.WDB.get('Batch Counters', label)
            self.label = label

        def load_images(self, directory_path, pattern):
            for file_name in glob.glob(os.path.join(glob.escape(directory_path), pattern), recursive=True):
                if file_name.lower().endswith(ALLOWED_EXT):
                    abs_file_path = os.path.abspath(file_name)
                    self.image_paths.append(abs_file_path)

        def get_image_by_id(self, image_id):
            if image_id < 0 or image_id >= len(self.image_paths):
                return (None, None)
            i = Image.open(self.image_paths[image_id])
            i = ImageOps.exif_transpose(i)
            return (i, os.path.basename(self.image_paths[image_id]))

        def get_next_image(self):
            if not self.image_paths:
                return (None, None)
            if self.index >= len(self.image_paths):
                self.index = 0
            image_path = self.image_paths[self.index]
            self.index += 1
            if self.index == len(self.image_paths):
                self.index = 0
            cstr(f'{self.label} Index: {self.index}').print()
            self.WDB.insert('Batch Counters', self.label, self.index)
            i = Image.open(image_path)
            i = ImageOps.exif_transpose(i)
            return (i, os.path.basename(image_path))

        def get_current_image(self):
            if self.index >= len(self.image_paths):
                self.index = 0
            image_path = self.image_paths[self.index]
            return os.path.basename(image_path)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        if kwargs['mode'] != 'single_image':
            return float("NaN")
        else:
            fl = Moyou_Image_Batch_Loader.BatchImageLoader(kwargs['path'], kwargs['label'], kwargs['pattern'])
            filename = fl.get_current_image()
            image = os.path.join(kwargs['path'], filename)
            sha = get_sha256(image)
            return sha
