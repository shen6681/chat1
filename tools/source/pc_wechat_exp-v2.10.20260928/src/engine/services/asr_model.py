"""语音识别（ASR）模型文件的定位、服务与下载。

浏览器端用 transformers.js 跑 Whisper；模型文件（config/tokenizer + onnx 权重）
需要本地可访问：

  1) 优先用户目录 %LOCALAPPDATA%\\WeChatEXP\\models（可写，打包版也能下载）
  2) 其次程序内置的 src/web/static/models（打包时随 exe 一起分发，只有小文件）

onnx 权重约 42MB、不适合塞进 exe，所以提供一键下载（默认 hf-mirror.com 国内镜像）。
"""
import os

# 模型清单：相对 HuggingFace 仓库根的路径
ASR_MODELS = {
    "Xenova/whisper-tiny": {
        "label": "Whisper Tiny（最小最快，中文识别较粗）",
        "files": [
            "config.json",
            "generation_config.json",
            "preprocessor_config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "onnx/encoder_model_quantized.onnx",
            "onnx/decoder_model_merged_quantized.onnx",
        ],
        "sizeMb": 41.6,
        "recommended": False,
    },
    "Xenova/whisper-base": {
        "label": "Whisper Base（默认：体积与中文准确度均衡）",
        "files": [
            "config.json",
            "generation_config.json",
            "preprocessor_config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "onnx/encoder_model_quantized.onnx",
            "onnx/decoder_model_merged_quantized.onnx",
        ],
        "sizeMb": 76.0,
        "recommended": True,
    },
    "Xenova/whisper-small": {
        "label": "Whisper Small（中文更准，下载较大）",
        "files": [
            "config.json",
            "generation_config.json",
            "preprocessor_config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "onnx/encoder_model_quantized.onnx",
            "onnx/decoder_model_merged_quantized.onnx",
        ],
        "sizeMb": 240.2,
        "recommended": False,
    },
}

# 下载源：(显示名, base url)   —— 国内默认走 hf-mirror，HF 官方作为备选
MODEL_MIRRORS = [
    ("hf-mirror.com（国内镜像，推荐）", "https://hf-mirror.com"),
    ("HuggingFace 官方（需能访问外网）", "https://huggingface.co"),
]

DEFAULT_MODEL = "Xenova/whisper-base"


def user_model_dir() -> str:
    """用户可写的模型目录（打包版也能往里下载）。"""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "WeChatEXP", "models")


def bundled_model_dir() -> str:
    """随程序分发的模型目录（src/web/static/models 或 exe 解包目录）。"""
    import sys as _sys
    bundle = getattr(_sys, "_MEIPASS", None)
    if bundle:
        return os.path.join(bundle, "src", "web", "static", "models")
    here = os.path.dirname(os.path.abspath(__file__))          # engine/services
    src = os.path.dirname(os.path.dirname(here))               # src
    return os.path.join(src, "web", "static", "models")


def model_roots():
    """查找顺序：用户目录 → 内置目录。"""
    return [user_model_dir(), bundled_model_dir()]


def resolve_model_file(model: str, relpath: str):
    """按顺序返回第一个存在的模型文件路径；都不存在返回 None。"""
    rel = relpath.replace("/", os.sep)
    for root in model_roots():
        p = os.path.join(root, model.replace("/", os.sep), rel)
        if os.path.isfile(p):
            return p
    return None


def model_status(model: str = DEFAULT_MODEL) -> dict:
    """模型文件就绪情况（缺哪些、还差多少 MB、下载源）。"""
    spec = ASR_MODELS.get(model)
    if not spec:
        return {"error": "unknown_model", "model": model, "files": [], "complete": False}
    files = []
    missing_bytes = 0
    for rel in spec["files"]:
        found = resolve_model_file(model, rel)
        size = os.path.getsize(found) if found else 0
        files.append({"name": rel, "exists": bool(found), "sizeMb": round(size / 1048576, 2),
                      "path": found or ""})
        if not found:
            missing_bytes += 0  # 实际大小下载时才知；这里只统计缺失个数
    missing = [f["name"] for f in files if not f["exists"]]
    return {
        "model": model,
        "label": spec["label"],
        "files": files,
        "complete": not missing,
        "missing": missing,
        "sizeMb": spec["sizeMb"],
        "userDir": user_model_dir(),
        "bundledDir": bundled_model_dir(),
        "mirrors": [{"name": n, "url": u} for n, u in MODEL_MIRRORS],
        "available": [{"model": m, "label": s["label"], "sizeMb": s["sizeMb"],
                       "recommended": bool(s.get("recommended"))}
                      for m, s in ASR_MODELS.items()],
    }


def download_model(model: str = DEFAULT_MODEL, base_url: str = None,
                   progress_fn=None, dest_root: str = None) -> dict:
    """把缺失的模型文件下载到用户模型目录。

    progress_fn(msg, pct) 用于回传进度；返回 {downloaded, skipped, bytes, dir}。
    """
    import urllib.request
    if progress_fn is None:
        progress_fn = lambda msg, pct=0: None
    spec = ASR_MODELS.get(model)
    if not spec:
        raise ValueError("未知模型: " + str(model))
    base = (base_url or MODEL_MIRRORS[0][1]).rstrip("/")
    root = os.path.join(dest_root or user_model_dir(), model.replace("/", os.sep))
    os.makedirs(root, exist_ok=True)

    downloaded = skipped = 0
    total_bytes = 0
    files = spec["files"]
    for idx, rel in enumerate(files):
        target = os.path.join(root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.isfile(target) and os.path.getsize(target) > 0:
            skipped += 1
            progress_fn("已存在，跳过 %s" % rel, (idx + 1) / float(len(files)))
            continue
        url = "%s/%s/resolve/main/%s" % (base, model, rel)
        progress_fn("下载 %s …" % rel, idx / float(len(files)))
        tmp = target + ".part"
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, open(tmp, "wb") as out:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
                    total_bytes += len(chunk)
            os.replace(tmp, target)
        except Exception as e:
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            raise IOError("下载 %s 失败: %s（可在界面上换一个下载源重试）" % (rel, e))
        downloaded += 1
        progress_fn("完成 %s" % rel, (idx + 1) / float(len(files)))

    return {"downloaded": downloaded, "skipped": skipped,
            "bytes": total_bytes, "dir": root, "mirror": base}
