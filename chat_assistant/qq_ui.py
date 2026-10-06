"""An actual QQ export workflow: connect, read a private chat, export or archive."""
from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from .qq_export import QQHistoryClient, export_plain_database, tool_root


class QQExportDialog:
    def __init__(self, center):
        from .app import BG, PANEL, TEXT, MUTED, TEAL, BORDER, label, button, text_box, set_text
        self.center=center;self.app=center.app;self.q=queue.Queue();self.cancel=threading.Event();self.busy=False;self.bundle=None;self.export_data=None;self.client=None;self.friends=[];self.account=None
        self.window=center.dialog("QQ 导出中心", "940x780")
        self.window.minsize(850,700);self.window.configure(bg=BG)
        self.window.protocol("WM_DELETE_WINDOW",self.close)
        header=tk.Frame(self.window,bg=BG,padx=24,pady=20);header.pack(fill="x")
        label(header,"QQ 导出中心",24,TEXT,True).pack(anchor="w")
        label(header,"连接记录服务  →  选择一个私聊  →  预览并存档",10,MUTED).pack(anchor="w",pady=(7,0))
        tabs=ttk.Notebook(self.window);tabs.pack(fill="both",expand=True,padx=24,pady=(0,16))
        online=tk.Frame(tabs,bg=PANEL,padx=20,pady=18);offline=tk.Frame(tabs,bg=PANEL,padx=20,pady=18)
        tabs.add(online,text="在线读取 QQ 记录");tabs.add(offline,text="QQNT 数据库导出")
        self.address=tk.StringVar(value="http://127.0.0.1:3000");self.token=tk.StringVar();self.friend_var=tk.StringVar();self.limit=tk.StringVar(value="1000")
        # Reserve the actions before the growing status area so they stay visible.
        footer=tk.Frame(online,bg=PANEL);footer.pack(side="bottom",fill="x",pady=(14,0))
        self.import_button=button(footer,"03  预览并导入存档",self.import_result,True,state="disabled");self.import_button.pack(side="right")
        self.save_button=button(footer,"另存为 JSON",self.save_result,state="disabled");self.save_button.pack(side="right",padx=8)
        label(online,"01  连接本机 QQ 记录服务",13,TEXT,True).pack(anchor="w")
        label(online,"支持 NapCat / LLOneBot 的 OneBot HTTP 接口。QQ 登录页只是连接器，记录在这里读取和导出。",9,MUTED,wraplength=820).pack(anchor="w",pady=(6,12))
        fields=tk.Frame(online,bg=PANEL);fields.pack(fill="x")
        for caption,var,secret in [("HTTP 地址",self.address,False),("HTTP Token",self.token,True)]:
            row=tk.Frame(fields,bg=PANEL);row.pack(fill="x",pady=4)
            label(row,caption,9,MUTED,width=13).pack(side="left")
            tk.Entry(row,textvariable=var,bg=BG,fg=TEXT,relief="flat",show="●" if secret else "",insertbackground=TEAL).pack(side="left",fill="x",expand=True,ipady=8)
        row=tk.Frame(online,bg=PANEL);row.pack(fill="x",pady=(8,16))
        self.connect_button=button(row,"连接并加载好友",self.connect,True);self.connect_button.pack(side="left")
        button(row,"打开 QQ 连接器",self.connector,padx=10).pack(side="left",padx=8)
        button(row,"连接设置说明",self.connection_help,padx=10).pack(side="left")
        self.login_note=tk.StringVar(value="未连接 · 先启用 OneBot HTTP 服务，通常使用本机 3000 端口")
        tk.Label(online,textvariable=self.login_note,bg=PANEL,fg=TEAL,anchor="w",font=("Microsoft YaHei UI",9),wraplength=800).pack(fill="x",pady=(0,16))
        label(online,"02  选择要读取的私聊",13,TEXT,True).pack(anchor="w")
        row=tk.Frame(online,bg=PANEL);row.pack(fill="x",pady=12)
        self.friend_combo=ttk.Combobox(row,textvariable=self.friend_var,state="readonly",width=45);self.friend_combo.pack(side="left",fill="x",expand=True)
        label(row,"最多",9,MUTED).pack(side="left",padx=(14,6))
        ttk.Combobox(row,textvariable=self.limit,values=["200","1000","5000","10000","30000"],width=8).pack(side="left")
        label(row,"条文本",9,MUTED).pack(side="left",padx=(6,0))
        row=tk.Frame(online,bg=PANEL);row.pack(fill="x")
        self.read_button=button(row,"读取所选聊天",self.read_history,True,state="disabled");self.read_button.pack(side="left")
        self.cancel_button=button(row,"取消读取",self.cancel.set,state="disabled");self.cancel_button.pack(side="left",padx=8)
        self.progress=ttk.Progressbar(online,mode="indeterminate",style="Signal.Horizontal.TProgressbar");self.progress.pack(fill="x",pady=(18,12))
        self.status=tk.StringVar(value="读取后可以直接存档，也可以另存为 ChatLab JSON。尚未读取任何私人记录。")
        status_area=tk.Frame(online,bg=BG);status_area.pack(fill="both",expand=True)
        status_box=text_box(status_area,height=4,readonly=True)
        status_scroll=ttk.Scrollbar(status_area,orient="vertical",command=status_box.yview)
        status_box.configure(yscrollcommand=status_scroll.set,fg=MUTED)
        status_scroll.pack(side="right",fill="y");status_box.pack(side="left",fill="both",expand=True)
        self.status.trace_add("write",lambda *_:set_text(status_box,self.status.get(),True))
        set_text(status_box,self.status.get(),True)
        label(offline,"QQNT_Export 3.3 · 数据库导出",15,TEXT,True).pack(anchor="w")
        label(offline,"从已解密的 nt_msg.db 导出私聊 ChatLab JSON，完成后直接导入。\n加密原库不能直接导出；没有解密副本时请用“在线读取 QQ 记录”。",10,MUTED,wraplength=810).pack(anchor="w",pady=(10,20))
        self.db_var=tk.StringVar();self.output_var=tk.StringVar(value=str(self.app.store.directory/"qq-exports"));self.filter_var=tk.StringVar()
        for caption,var,picker in [("已解密数据库目录",self.db_var,True),("输出目录",self.output_var,True),("只导出这些 QQ 号",self.filter_var,False)]:
            row=tk.Frame(offline,bg=PANEL);row.pack(fill="x",pady=8)
            label(row,caption,9,MUTED,width=20).pack(side="left")
            tk.Entry(row,textvariable=var,bg=BG,fg=TEXT,relief="flat",insertbackground=TEAL).pack(side="left",fill="x",expand=True,ipady=8)
            if picker:button(row,"选择",lambda v=var:self.choose_directory(v),padx=10,pady=6).pack(side="left",padx=(8,0))
        label(offline,"QQ 号可留空以导出全部私聊；多个 QQ 号用逗号分隔。本页不要求你再次登录 QQ。",9,MUTED,wraplength=800).pack(anchor="w",pady=(6,16))
        row=tk.Frame(offline,bg=PANEL);row.pack(fill="x")
        self.offline_button=button(row,"导出私聊 JSON",self.offline_export,True);self.offline_button.pack(side="left")
        button(row,"数据库准备说明",lambda:webbrowser.open("https://qqbackup.github.io/QQDecrypt/"),padx=10).pack(side="left",padx=8)
        button(row,"导入已有 JSON",lambda:(self.close(),center.pick_file()),padx=10).pack(side="left")
        self.offline_note=tk.StringVar(value="使用本机 QQNT_Export v3.3.0（上游预发布版）。建议选择已解密的数据库副本，导出文件会保存在上方目录。")
        tk.Label(offline,textvariable=self.offline_note,bg=BG,fg=MUTED,font=("Microsoft YaHei UI",10),anchor="nw",justify="left",padx=14,pady=14,wraplength=780).pack(fill="both",expand=True,pady=(18,0))
        self.window.after(100,self.poll)

    def choose_directory(self,var):
        path=filedialog.askdirectory(parent=self.window)
        if path:var.set(path)

    def connection_help(self):
        from .app import BG, PANEL, TEXT, MUTED, label, button
        window=self.center.dialog("连接 QQ 记录服务","780x520")
        label(window,"登录之后，还需要启用记录接口",18,TEXT,True).pack(anchor="w",padx=24,pady=(24,16))
        steps=[
            ("01  打开连接器管理页","启动 NapCat / LLOneBot 并登录 QQ。NapCat 的 WebUI 地址由启动日志显示，通常是本机 6099 端口。"),
            ("02  新建 HTTP 服务端","进入网络配置，新建 HTTP 服务端，监听地址填 127.0.0.1，端口填 3000，设置 HTTP Token，并保存、启用。若端口被占用，可换一个。"),
            ("03  回到 QQ 导出中心","填写 http://127.0.0.1:3000 和刚设置的 HTTP Token，点击连接并加载好友，再选择私聊读取、导出或存档。"),
        ]
        for title,body in steps:
            label(window,title,11,TEXT,True).pack(anchor="w",padx=24,pady=(8,5))
            label(window,body,10,MUTED,wraplength=725).pack(anchor="w",padx=24,pady=(0,8))
        label(window,"WebUI 登录密码与 HTTP Token 是两个设置；导出中心使用 HTTP 服务端的地址和 Token。",9,MUTED,wraplength=725).pack(anchor="w",padx=24,pady=8)
        row=tk.Frame(window,bg=PANEL);row.pack(side="bottom",fill="x",padx=24,pady=18)
        button(row,"NapCat 官方设置文档",lambda:webbrowser.open("https://napneko.github.io/config/basic"),padx=12).pack(side="left")
        def done():
            window.destroy()
            if self.window.winfo_exists():self.window.grab_set()
        window.protocol("WM_DELETE_WINDOW",done)
        button(row,"返回导出中心",done,True).pack(side="right")

    def connector(self):
        path=tool_root()/"QQChatExporter"/"NapCat-QCE-Windows-x64"/"launcher-user.bat"
        if path.exists():
            os.startfile(str(path),cwd=str(path.parent))
            self.status.set("已启动 QQ 连接器。登录后在其设置中启用 OneBot HTTP（3000），填入相同 HTTP Token，然后点击连接。连接器负责提供记录，导出操作在本窗口。")
        else:messagebox.showinfo("QQ 记录服务","请先启动你本机的 NapCat 或 LLOneBot，并启用 OneBot HTTP 服务；然后在这里连接并读取。",parent=self.window)

    def work(self,operation,callback,cancellable=True):
        if self.busy:return
        self.busy=True;self.cancel.clear();self.progress.start(12)
        for widget in [self.connect_button,self.read_button,self.offline_button,self.import_button,self.save_button]:widget.configure(state="disabled")
        self.cancel_button.configure(state="normal" if cancellable else "disabled")
        def worker():
            try:self.q.put((callback,operation(),None))
            except Exception as error:self.q.put((callback,None,str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        if not self.window.winfo_exists():return
        try:
            callback,result,error=self.q.get_nowait()
            if callback=="progress":self.status.set(f"正在读取… 已取得 {result} 条文本记录。");self.window.after(100,self.poll);return
            self.busy=False;self.progress.stop();self.cancel_button.configure(state="disabled")
            self.connect_button.configure(state="normal");self.offline_button.configure(state="normal")
            self.read_button.configure(state="normal" if self.client else "disabled")
            if error:self.status.set(error);self.offline_note.set(error);messagebox.showerror("QQ 导出未完成",error,parent=self.window)
            else:callback(result)
            if self.bundle:
                self.import_button.configure(state="normal");self.save_button.configure(state="normal")
        except queue.Empty:pass
        if self.window.winfo_exists():self.window.after(100,self.poll)

    def connect(self):
        try:client=QQHistoryClient(self.address.get(),self.token.get())
        except ValueError as e:messagebox.showerror("地址不正确",str(e),parent=self.window);return
        self.client=None;self.bundle=None;self.export_data=None;self.friend_combo.configure(values=[]);self.friend_var.set("")
        def ready(result):
            self.account,self.friends=result;self.client=client
            self.friend_combo.configure(values=[f"{f.get('remark') or f.get('nickname') or f['user_id']}  ·  {f['user_id']}" for f in self.friends])
            if self.friends:self.friend_combo.current(0)
            self.login_note.set(f"已连接 {self.account.get('nickname','QQ')} · {self.account['user_id']} · 找到 {len(self.friends)} 位好友")
            self.read_button.configure(state="normal" if self.friends else "disabled")
            self.status.set("连接成功。选择一个联系人，再点击“读取所选聊天”；连接本身不会读取聊天正文。")
        self.work(client.connect,ready)

    def read_history(self):
        if not self.client or self.friend_combo.current()<0:return
        friend=self.friends[self.friend_combo.current()];client=self.client
        try:limit=int(self.limit.get());assert 1<=limit<=30000
        except (ValueError,AssertionError):messagebox.showerror("数量不正确","请输入 1 到 30000 之间的读取数量。",parent=self.window);return
        self.bundle=None;self.export_data=None
        def ready(result):
            self.bundle,self.export_data=result
            count=len(self.bundle.conversations[0].messages)
            self.status.set(f"已读取 {count} 条文本消息。\n\n"+"\n".join(self.bundle.warnings)+"\n\n点击右下角预览并确认“哪位是我”，再写入本地档案。")
        self.work(lambda:client.history(self.account['user_id'],friend['user_id'],friend.get('remark') or friend.get('nickname') or str(friend['user_id']),limit,lambda count:self.q.put(("progress",count,None)),self.cancel),ready)

    def import_result(self):
        if self.bundle:
            bundle=self.bundle;self.close();self.center.preview(bundle)

    def save_result(self):
        if not self.export_data:return
        path=filedialog.asksaveasfilename(parent=self.window,title="导出 QQ 私聊记录",defaultextension=".json",initialfile="QQ私聊记录.json",filetypes=[("ChatLab JSON","*.json")])
        if path:
            try:Path(path).write_text(json.dumps(self.export_data,ensure_ascii=False,indent=2),encoding="utf-8");self.status.set("私聊记录已导出为 JSON，也可以继续导入联系人档案。")
            except OSError:messagebox.showerror("保存失败","无法写入所选位置，请更换目录。",parent=self.window)

    def offline_export(self):
        if not self.db_var.get().strip() or not self.output_var.get().strip():messagebox.showerror("请选择目录","请先选择数据库目录和输出目录。",parent=self.window);return
        db=Path(self.db_var.get());output=Path(self.output_var.get())/datetime.now().strftime("export-%Y%m%d-%H%M%S-%f");filters=self.filter_var.get()
        self.offline_note.set("正在运行 QQNT_Export，导出完成后会列出可导入的私聊文件…")
        def ready(files):
            self.offline_note.set(f"导出完成：{len(files)} 个私聊 JSON。\n输出目录：{output}\n点击文件名打开导入预览。")
            from .app import BG, PANEL, TEXT, TEAL, label, button
            chooser=self.center.dialog("选择 QQ 私聊导出文件","780x570")
            label(chooser,"选择要存入档案的私聊",17,TEXT,True).pack(anchor="w",padx=20,pady=18)
            listing=tk.Listbox(chooser,bg=BG,fg=TEXT,selectbackground=TEAL,selectforeground="white",relief="flat",exportselection=False)
            listing.pack(fill="both",expand=True,padx=20)
            for file in files:listing.insert("end",file.stem)
            if files:listing.selection_set(0)
            def import_file():
                index=listing.curselection()
                if index:
                    file=files[index[0]];chooser.destroy();self.close()
                    from .importers import load_file
                    self.center.run(lambda:load_file(file),self.center.preview)
            button(chooser,"预览并导入",import_file,True).pack(anchor="e",padx=20,pady=18)
        self.work(lambda:export_plain_database(db,output,filters),ready,cancellable=False)

    def close(self):
        self.cancel.set()
        if self.window.winfo_exists():self.window.destroy()
