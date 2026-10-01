from __future__ import annotations

import base64
import ctypes
import json
import os
from dataclasses import asdict, fields
from pathlib import Path

from .core import Settings


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(data: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise RuntimeError("API Key 加密保存仅支持 Windows。可关闭“记住密钥”后使用。")
    buffer = ctypes.create_string_buffer(data)
    source = _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = _Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        function = crypt32.CryptUnprotectData
        function.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_Blob)]
        ok = function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result))
    else:
        function = crypt32.CryptProtectData
        function.argtypes = [ctypes.POINTER(_Blob), ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_Blob)]
        ok = function(ctypes.byref(source), "ChatReplyAssistant", None, None, None, 1, ctypes.byref(result))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


class SettingsStore:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ChatReplyAssistant"
        self.path = self.directory / "settings.json"

    def save(self, settings: Settings) -> None:
        data = asdict(settings)
        for name in ("chat_key", "jev_key"):
            key = data.pop(name)
            if key and settings.remember_keys:
                data[name + "_encrypted"] = base64.b64encode(_crypt(key.encode("utf-8"))).decode("ascii")
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def load(self) -> Settings:
        if not self.path.exists():
            settings = Settings()
        else:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = {f.name for f in fields(Settings)} - {"chat_key", "jev_key"}
            settings = Settings(**{k: v for k, v in data.items() if k in allowed})
            for name in ("chat_key", "jev_key"):
                if settings.remember_keys and data.get(name + "_encrypted"):
                    setattr(settings, name, _crypt(base64.b64decode(data[name + "_encrypted"]), decrypt=True).decode("utf-8"))
            settings.validate(require_keys=False)
        settings.chat_key = settings.chat_key or os.environ.get("DEEPSEEK_API_KEY", "")
        settings.jev_key = settings.jev_key or os.environ.get("TYPESAFE_API_KEY", "")
        return settings
