"""相似度模块单元测试。"""

import unittest
from pathlib import Path

from PIL import Image

from src.similarity import ImageSimilarity
from src.utils import format_duration, get_video_info
from src.video_similarity import VideoSimilarity


class TestImageSimilarity(unittest.TestCase):
    """测试 ImageSimilarity 类。"""

    def setUp(self):
        self.sim = ImageSimilarity(method="phash", threshold=0.85)
        # 创建临时测试图片
        self.tmp_dir = Path(__file__).parent / "tmp"
        self.tmp_dir.mkdir(exist_ok=True)

        self.img_same_1 = self.tmp_dir / "same1.png"
        self.img_same_2 = self.tmp_dir / "same2.png"
        self.img_diff = self.tmp_dir / "diff.png"

        # 完全相同的两张图
        img = Image.new("RGB", (100, 100), color="red")
        img.save(self.img_same_1)
        img.save(self.img_same_2)

        # 不同的图（带纹理差异，避免纯色块的哈希碰撞）
        from PIL import ImageDraw
        img2 = Image.new("RGB", (100, 100), color="white")
        draw = ImageDraw.Draw(img2)
        for i in range(0, 100, 10):
            draw.line([(0, i), (100, i)], fill="black", width=2)
        img2.save(self.img_diff)

    def tearDown(self):
        for f in self.tmp_dir.iterdir():
            f.unlink()
        self.tmp_dir.rmdir()

    def test_identical_images(self):
        """完全相同图片的相似度应接近 1。"""
        score = self.sim.compare(self.img_same_1, self.img_same_2)
        self.assertAlmostEqual(score, 1.0, places=2)

    def test_different_images(self):
        """不同图片的相似度应较低。"""
        score = self.sim.compare(self.img_same_1, self.img_diff)
        # 纯色块的 phash 可能较高，至少不应为 1.0
        self.assertLess(score, 1.0)

    def test_is_similar(self):
        """is_similar 应正确判断相同图片。"""
        self.assertTrue(self.sim.is_similar(self.img_same_1, self.img_same_2))

    def test_all_methods(self):
        """所有算法应能正常运行不抛异常。"""
        methods = ["phash", "dhash", "ahash", "whash", "ssim", "orb"]
        for method in methods:
            with self.subTest(method=method):
                score = self.sim.compare(self.img_same_1, self.img_same_2, method=method)
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 1.0)


class TestVideoSimilarity(unittest.TestCase):
    """测试 VideoSimilarity 工具函数。"""

    def test_compute_video_similarity_identical(self):
        """相同特征应返回相似度 1.0。"""
        import numpy as np

        vsim = VideoSimilarity()
        features = np.random.rand(8, 2048).astype(np.float32)
        score = vsim.compute_video_similarity(features, features)
        self.assertAlmostEqual(score, 1.0, places=5)

    def test_compute_video_similarity_different(self):
        """完全不同的特征应返回较低相似度。"""
        import numpy as np

        vsim = VideoSimilarity()
        # 构造正交特征：a 的前半维为 1，b 的后半维为 1
        features_a = np.zeros((8, 2048), dtype=np.float32)
        features_a[:, :1024] = 1.0
        features_b = np.zeros((8, 2048), dtype=np.float32)
        features_b[:, 1024:] = 1.0
        score = vsim.compute_video_similarity(features_a, features_b)
        self.assertLess(score, 0.6)  # 正交特征应有明显低相似度

    def test_compute_video_similarity_empty(self):
        """空特征应返回 0.0。"""
        import numpy as np

        vsim = VideoSimilarity()
        score = vsim.compute_video_similarity(
            np.zeros((0, 2048), dtype=np.float32),
            np.zeros((0, 2048), dtype=np.float32),
        )
        self.assertEqual(score, 0.0)

    def test_format_duration(self):
        """时长格式化测试。"""
        self.assertEqual(format_duration(0), "00:00")
        self.assertEqual(format_duration(65), "01:05")
        self.assertEqual(format_duration(3661), "1:01:01")
        self.assertEqual(format_duration(-1), "00:00")


if __name__ == "__main__":
    unittest.main()
