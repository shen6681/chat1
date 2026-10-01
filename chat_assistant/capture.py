from __future__ import annotations

import ctypes
import os
import re
from dataclasses import dataclass
from ctypes import wintypes

import mss
from PIL import Image

from .core import Message, Region, Transcript


class CaptureUnavailable(RuntimeError):
    pass


def enable_dpi_awareness() -> None:
    if os.name == "nt":
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except (AttributeError, OSError):
                pass


def _user32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    return user32


def window_at(x: int, y: int) -> int:
    user32 = _user32()
    return int(user32.GetAncestor(user32.WindowFromPoint(wintypes.POINT(x, y)), 2) or 0)


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    if not _user32().GetWindowRect(hwnd, ctypes.byref(rect)):
        raise CaptureUnavailable("聊天窗口已关闭，请重新框选。")
    return rect.left, rect.top, rect.right, rect.bottom


@dataclass(frozen=True)
class CaptureTarget:
    region: Region
    hwnd: int
    original_window: tuple[int, int, int, int]
    title: str

    @classmethod
    def bind(cls, region: Region) -> "CaptureTarget":
        hwnd = window_at(region.left + region.width // 2, region.top + region.height // 2)
        if not hwnd:
            raise CaptureUnavailable("未找到选区所在窗口，请重新框选 QQ 或微信聊天区。")
        bounds = window_rect(hwnd)
        if region.left < bounds[0] or region.top < bounds[1] or region.left + region.width > bounds[2] or region.top + region.height > bounds[3]:
            raise CaptureUnavailable("选区跨出了聊天窗口，请只框选同一窗口内的消息气泡。")
        title = ctypes.create_unicode_buffer(512)
        _user32().GetWindowTextW(hwnd, title, 512)
        return cls(region, hwnd, bounds, title.value or "已选窗口")

    def resolve(self) -> Region:
        user32 = _user32()
        if not user32.IsWindow(self.hwnd) or user32.IsIconic(self.hwnd):
            raise CaptureUnavailable("聊天窗口已关闭或最小化，读取已暂停。")
        current = window_rect(self.hwnd)
        original = self.original_window
        if (current[2] - current[0], current[3] - current[1]) != (original[2] - original[0], original[3] - original[1]):
            raise CaptureUnavailable("聊天窗口大小已变化，请重新框选聊天区。")
        region = Region(self.region.left + current[0] - original[0], self.region.top + current[1] - original[1], self.region.width, self.region.height)
        # Sampling across the entire crop catches common overlapping windows.
        # This is a visibility guard, not an OCR or perfect occlusion guarantee.
        for fx in (.05, .5, .95):
            for fy in (.05, .5, .95):
                if window_at(int(region.left + fx * region.width), int(region.top + fy * region.height)) != self.hwnd:
                    raise CaptureUnavailable("聊天区被其他窗口遮挡，暂缓读取；露出聊天区后会继续。")
        return region


def grab(region: Region) -> Image.Image:
    with mss.mss() as screen:
        shot = screen.grab(region.to_dict())
    return Image.frombytes("RGB", shot.size, shot.rgb)


def rows_to_transcript(rows, width: int, self_on_right: bool = True) -> Transcript:
    lines = []
    for box, text, confidence in rows or []:
        text = str(text).strip()
        if not text or float(confidence) < .5:
            continue
        xs, ys = [float(p[0]) for p in box], [float(p[1]) for p in box]
        left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
        centered = abs(left - (width - right)) < width * .08
        if centered and re.fullmatch(r"(?:今天|昨天|前天|星期[一二三四五六日天]|\d{1,4}[-年/.月:]\d{1,2}.*|\d{1,2}:\d{2})(?:\s.*)?", text):
            continue
        side = "未知" if centered else "右" if width - right < left else "左"
        speaker = "未确认" if side == "未知" else "我" if (side == "右") == self_on_right else "对方"
        lines.append((top, left, bottom, right, speaker, text, float(confidence)))
    lines.sort(key=lambda line: (round(line[0] / 8), line[1]))
    messages: list[Message] = []
    previous = None
    for line in lines:
        top, left, bottom, right, speaker, text, confidence = line
        if previous and messages and previous[4] == speaker and 0 <= top - previous[2] <= max(5, (bottom - top) * .7) and abs(left - previous[1]) < width * .15:
            messages[-1].text += "\n" + text
            messages[-1].confidence = min(messages[-1].confidence, confidence)
        else:
            messages.append(Message(speaker, text, confidence))
        previous = line
    warnings = ["说话人按气泡左右位置推测，请校对；昵称、图片、表情或长气泡可能识别不完整。"]
    if any(m.speaker == "未确认" for m in messages):
        warnings.append("部分文字居中，说话人未确认。")
    if any(m.confidence < .8 for m in messages):
        warnings.append("存在置信度较低的识别文字，请先校对。")
    return Transcript(messages[-40:], "屏幕 OCR", warnings)


class LocalOCR:
    def __init__(self):
        self.engine = None

    def recognize(self, image: Image.Image, self_on_right: bool = True) -> Transcript:
        if self.engine is None:
            from rapidocr_onnxruntime import RapidOCR
            # Bundled models; no chat data or image is sent to an OCR service.
            self.engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
        import numpy as np
        rows, _ = self.engine(np.asarray(image)[:, :, ::-1].copy())
        return rows_to_transcript(rows, image.width, self_on_right)
