"""Verify the ZIP from an extracted path with spaces and an empty app profile."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path

from package_clean_portable import ROOT, ZIP, extract_checked, sha256


def main():
    parent=(ROOT/"verification-temp").resolve()
    work=(parent/("portable-"+uuid.uuid4().hex)).resolve()
    if not work.is_relative_to(parent) or work.exists():
        raise ValueError("Unexpected verification target")
    work.mkdir(parents=True)
    report={"version":"2.6.1","zip":str(ZIP),"synthetic_only":True,"real_api_requests":0}
    try:
        target=work/"解压 验证"
        extract_checked(ZIP,target)
        package=target/"chat1_便携版"
        manifest=json.loads((package/"文件清单.json").read_text(encoding="utf-8"))
        report["manifest_hashes"]=all(sha256(package/item["file"])==item["sha256"] for item in manifest["files"])
        if not report["manifest_hashes"]:
            raise ValueError("Extracted-file digest mismatch")
        env=os.environ.copy()
        env["LOCALAPPDATA"]=str(work/"fresh-local")
        env["APPDATA"]=str(work/"fresh-roaming")
        env["PATH"]=str(Path(env["WINDIR"])/"System32")+os.pathsep+env["WINDIR"]
        for key in list(env):
            if key.upper().startswith("PYTHON") or key.upper() in {"DEEPSEEK_API_KEY","TYPESAFE_API_KEY","OPENAI_API_KEY"}:
                env.pop(key,None)
        executable=package/"ChatReplyAssistant.exe"
        print("Extracted ZIP hashes match; testing with an empty profile and no Python on PATH.",flush=True)
        diagnostic=work/"self-test.json"
        process=subprocess.run([str(executable),"--self-test",str(diagnostic)],cwd=package,env=env,timeout=90,
                               creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),capture_output=True)
        report["self_test_exit"]=process.returncode
        report["self_test"]=json.loads(diagnostic.read_text(encoding="utf-8")) if diagnostic.exists() else {}
        if process.returncode!=0 or not report["self_test"].get("ok"):
            raise ValueError("Extracted EXE offline self-test failed")
        print("Extracted EXE self-test passed; testing the launch shortcut.",flush=True)
        # Static task-owned paths are quoted; no user text or filesystem operations are composed in cmd.
        snapshot=work/"startup.png"
        command='call "'+str(package/"启动程序.cmd")+'" --smoke-test "'+str(snapshot)+'"'
        started=time.monotonic()
        # Supply cmd's command line directly; list2cmdline's backslash quote escaping is for C argv parsers.
        cmdline='"'+str(Path(env["WINDIR"])/"System32"/"cmd.exe")+'" /d /c '+command
        launcher=subprocess.run(cmdline,
                                cwd=package,env=env,timeout=20,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),capture_output=True)
        report["launcher_exit"]=launcher.returncode
        if launcher.returncode!=0:
            raise ValueError("Launch shortcut command failed: "+str(launcher.returncode))
        while not snapshot.exists() and time.monotonic()-started<40:
            time.sleep(.2)
        if launcher.returncode!=0 or not snapshot.exists():
            raise ValueError("The extracted launch shortcut did not start the GUI")
        from PIL import Image
        with Image.open(snapshot) as screenshot:
            report["gui_dimensions"]=list(screenshot.size)
            if screenshot.width<1000 or screenshot.height<700:
                raise ValueError("Unexpected GUI snapshot")
        data=Path(env["LOCALAPPDATA"])/"ChatReplyAssistant"
        database=sqlite3.connect(data/"archives.sqlite3")
        report["fresh_profile_empty"]=database.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]==0 and database.execute("SELECT COUNT(*) FROM messages").fetchone()[0]==0
        database.close()
        report["no_shared_api_settings"]=not (data/"settings.json").exists()
        report["no_python_required"]=True
        # Both helpers and the launcher's expected paths remain valid after moving the package.
        required=("tools/WeChatEXP/wechat_exp_2.10.20260928.exe","tools/QQNT_Export/QQNT_Export_3.3.0.exe",
                  "tools/QQChatExporter/NapCat-QCE-Windows-x64/launcher-user.bat")
        report["exporter_paths_exist"]=all((package/name).is_file() for name in required)
        report["ok"]=all(report[k] for k in ("manifest_hashes","fresh_profile_empty","no_shared_api_settings","exporter_paths_exist"))
        if not report["ok"]:
            raise ValueError("Portable-package verification failed")
        shutil.copy2(snapshot,ROOT/"assets"/"portable-clean-startup.png")
    finally:
        (ROOT/"assets"/"portable-clean-verification.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        # Only the newly created task-owned directory is cleaned up.
        if work.is_relative_to(parent) and work.name.startswith("portable-"):
            for attempt in range(5):
                try:
                    shutil.rmtree(work)
                    break
                except PermissionError:
                    if attempt==4:
                        raise
                    time.sleep(.5)
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
