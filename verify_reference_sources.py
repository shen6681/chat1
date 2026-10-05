"""Verify the pinned reference source trees, ZIPs and original notices offline."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "tools/source/provenance.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes source directory: {relative}")
    return path


def verify(root: Path = ROOT) -> list[str]:
    manifest = json.loads((root / MANIFEST.relative_to(ROOT)).read_text(encoding="utf-8"))
    if manifest["schema_version"] != 1:
        raise ValueError("Unsupported reference-source manifest version")
    components = manifest["components"]
    if {item["name"] for item in components} != {"WeChatEXP", "QQNT_Export", "QQChatExporter", "NapCat"} or len(components) != 4:
        raise ValueError("Reference-source manifest must contain all four helpers")
    results = []
    for component in components:
        name = component["name"]
        files = component["files"]
        expected = {item["path"]: item for item in files}
        if len(files) != len(expected) or len(files) != component["file_count"]:
            raise ValueError(f"{name}: invalid or duplicate file inventory")
        stored = {item.get("stored_path", item["path"]) for item in files}
        if len(stored) != len(files):
            raise ValueError(f"{name}: duplicate stored source paths")
        source = checked_path(root, component["source_dir"])
        actual = {path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file()}
        if actual != stored:
            raise ValueError(f"{name}: missing={sorted(stored-actual)}, unexpected={sorted(actual-stored)}")
        for relative, item in expected.items():
            path = checked_path(source, item.get("stored_path", relative))
            data = path.read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if len(data) != item["size"] or sha256(data) != item["sha256"] or blob != item["git_blob"]:
                raise ValueError(f"{name}: source differs from pinned Git blob: {relative}")
        archive_path = checked_path(root, component["archive"])
        if sha256(archive_path.read_bytes()) != component["archive_sha256"]:
            raise ValueError(f"{name}: source ZIP hash mismatch")
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            prefix = component["archive_prefix"]
            wanted = {prefix + relative for relative in expected}
            if len(members) != len(wanted) or {item.filename for item in members} != wanted:
                raise ValueError(f"{name}: source ZIP inventory mismatch")
            for member in members:
                relative = member.filename[len(prefix):]
                if sha256(archive.read(member)) != expected[relative]["sha256"]:
                    raise ValueError(f"{name}: source ZIP content mismatch: {relative}")
        for notice in component["notices"]:
            data = checked_path(root, notice["path"]).read_bytes()
            if sha256(data) != notice["sha256"] or sha256(data) != expected[notice["source_path"]]["sha256"]:
                raise ValueError(f"{name}: upstream notice was changed: {notice['path']}")
        results.append(f"{name} {component['tag']}: {len(files)} files, ZIP and notices verified ({component['commit']})")
    return results


if __name__ == "__main__":
    try:
        for result in verify():
            print(result)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"Reference-source verification failed: {error}", file=sys.stderr)
        sys.exit(1)
