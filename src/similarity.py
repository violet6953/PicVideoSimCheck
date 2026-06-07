"""图片相似度计算模块，支持多种算法。"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Callable

import cv2
import imagehash
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

# Match numpy/BLAS thread count to CPU threads for parallel linear algebra
os.environ.setdefault("OMP_NUM_THREADS", str(os.cpu_count() or 20))
os.environ.setdefault("MKL_NUM_THREADS", str(os.cpu_count() or 20))
os.environ.setdefault("OPENBLAS_NUM_THREADS", str(os.cpu_count() or 20))


class ImageSimilarity:
    """提供多种图片相似度计算方法。"""

    def __init__(self, method: str = "phash", threshold: float = 0.85):
        """
        初始化相似度计算器。

        Args:
            method: 默认使用的相似度算法，可选 "phash", "dhash", "ahash", "whash",
                "histogram", "ssim", "orb"
            threshold: 判定为相似的阈值 (0~1)
        """
        self.method = method.lower()
        self.threshold = threshold
        self._hash_funcs: dict[str, Callable] = {
            "phash": imagehash.phash,
            "dhash": imagehash.dhash,
            "ahash": imagehash.average_hash,
            "whash": imagehash.whash,
        }

    def _load_image(self, image_input: str | Path | bytes) -> Image.Image:
        """统一加载为 PIL Image。"""
        if isinstance(image_input, (str, Path)):
            return Image.open(image_input).convert("RGB")
        if isinstance(image_input, bytes):
            return Image.open(io.BytesIO(image_input)).convert("RGB")
        raise TypeError(f"不支持的输入类型: {type(image_input)}")

    def _pil_to_cv(self, pil_img: Image.Image) -> np.ndarray:
        """PIL Image 转为 OpenCV BGR 格式。"""
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    def hash_similarity(self, img1, img2, hash_type: str | None = None) -> float:
        """
        基于感知哈希的相似度。
        返回 0~1 之间的值，1 表示完全相同。
        """
        hash_func = self._hash_funcs.get(hash_type or self.method)
        if hash_func is None:
            raise ValueError(f"不支持的哈希类型: {hash_type}")

        p1 = self._load_image(img1)
        p2 = self._load_image(img2)

        h1 = hash_func(p1)
        h2 = hash_func(p2)

        # Hamming distance / max bits -> dissimilarity
        max_bits = max(len(h1.hash) ** 2, len(h2.hash) ** 2)
        distance = h1 - h2
        return 1.0 - (distance / max_bits)

    def histogram_similarity(self, img1, img2) -> float:
        """
        基于颜色直方图的相似度（Correl 方法）。
        返回 0~1 之间的值，1 表示完全相同。
        """
        p1 = self._load_image(img1)
        p2 = self._load_image(img2)

        # 统一尺寸以减少偏差
        size = (256, 256)
        p1 = p1.resize(size)
        p2 = p2.resize(size)

        cv1 = self._pil_to_cv(p1)
        cv2 = self._pil_to_cv(p2)

        hist1 = cv2.calcHist([cv1], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        hist2 = cv2.calcHist([cv2], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])

        hist1 = cv2.normalize(hist1, hist1).flatten()
        hist2 = cv2.normalize(hist2, hist2).flatten()

        similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        return max(0.0, similarity)

    def ssim_similarity(self, img1, img2) -> float:
        """
        基于结构相似性指数 (SSIM) 的相似度。
        返回 0~1 之间的值，1 表示完全相同。
        """
        p1 = self._load_image(img1)
        p2 = self._load_image(img2)

        size = (256, 256)
        p1 = p1.resize(size)
        p2 = p2.resize(size)

        arr1 = np.array(p1)
        arr2 = np.array(p2)

        score, _ = ssim(arr1, arr2, channel_axis=2, full=True)
        return float(score)

    def orb_similarity(self, img1, img2) -> float:
        """
        基于 ORB 特征匹配的相似度。
        对旋转、缩放、光照有一定鲁棒性。
        返回 0~1 之间的值。
        """
        p1 = self._load_image(img1)
        p2 = self._load_image(img2)

        size = (512, 512)
        p1 = p1.resize(size)
        p2 = p2.resize(size)

        gray1 = cv2.cvtColor(np.array(p1), cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(np.array(p2), cv2.COLOR_RGB2GRAY)

        orb = cv2.ORB_create(nfeatures=500)
        kp1, des1 = orb.detectAndCompute(gray1, None)
        kp2, des2 = orb.detectAndCompute(gray2, None)

        if des1 is None or des2 is None:
            return 0.0

        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)

        if not matches:
            return 0.0

        # 按距离排序，取前 N 个好匹配
        matches = sorted(matches, key=lambda x: x.distance)
        good_matches = [m for m in matches if m.distance < 50]

        max_possible = min(len(kp1), len(kp2))
        if max_possible == 0:
            return 0.0

        return len(good_matches) / max_possible

    def compare(self, img1, img2, method: str | None = None) -> float:
        """
        使用指定方法计算两张图片的相似度。

        Args:
            img1: 图片路径或字节数据
            img2: 图片路径或字节数据
            method: 算法名称，None 则使用初始化时设置的默认值

        Returns:
            0~1 之间的相似度分数
        """
        method = (method or self.method).lower()

        if method in self._hash_funcs:
            return self.hash_similarity(img1, img2, method)
        if method == "histogram":
            return self.histogram_similarity(img1, img2)
        if method == "ssim":
            return self.ssim_similarity(img1, img2)
        if method == "orb":
            return self.orb_similarity(img1, img2)

        raise ValueError(f"不支持的相似度算法: {method}")

    def is_similar(self, img1, img2, method: str | None = None, threshold: float | None = None) -> bool:
        """判断两张图片是否相似。"""
        score = self.compare(img1, img2, method)
        return score >= (threshold or self.threshold)
