import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from chat_assistant.capture import LocalOCR


def synthetic_chat():
    image = Image.new("RGB", (760, 350), "#ededed")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 25)
    draw.rounded_rectangle((42, 42, 390, 102), radius=10, fill="white")
    draw.text((60, 55), "今天终于忙完了，有点累。", font=font, fill="#222222")
    draw.rounded_rectangle((340, 140, 710, 205), radius=10, fill="#95ec69")
    draw.text((358, 156), "辛苦啦，晚上想怎么放松？", font=font, fill="#222222")
    draw.rounded_rectangle((42, 245, 410, 305), radius=10, fill="white")
    draw.text((60, 259), "想看个电影，你有推荐吗？", font=font, fill="#222222")
    return image


class OCRIntegrationTests(unittest.TestCase):
    def test_real_ocr_on_synthetic_chinese_bubbles(self):
        image = synthetic_chat()
        transcript = LocalOCR().recognize(image)
        self.assertIn("电影", transcript.text)
        self.assertIn("辛苦", transcript.text)
        self.assertEqual([m.speaker for m in transcript.messages], ["对方", "我", "对方"])


if __name__ == "__main__":
    unittest.main()
