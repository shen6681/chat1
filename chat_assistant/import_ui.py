from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .importers import from_text, guess_columns, load_file, load_sqlite, sqlite_tables
from .weflow import WeFlowClient
from .ui_widgets import Card, ContactList, Tooltip


class ImportCenter:
    def __init__(self, app):
        from .app import BG, PANEL, TEXT, MUTED, TEAL, BORDER, ACCENT_LIGHT, label, button, text_box, set_text
        self.app, self.root = app, app.root
        self.style = (BG, PANEL, TEXT, MUTED, TEAL, label, button, text_box, set_text)
        self.queue = queue.Queue()
        self.busy = False
        self.page = tk.Frame(app.page_container, bg=BG)
        header=tk.Frame(self.page,bg=BG);header.pack(fill="x",pady=(0,10))
        title=tk.Frame(header,bg=BG);title.pack(side="left")
        label(title, "你的对话旅程", 23, TEXT, True).pack(anchor="w")
        label(title, "保存文字档案，逐条读懂互动。", 9, MUTED).pack(anchor="w", pady=(3, 0))
        self.import_button=button(header,"+  导入记录",self.pick_file,True)
        self.import_button.pack(side="right",anchor="s")
        actions = tk.Frame(self.page, bg=BG, padx=0, pady=0)
        actions.pack(fill="x")
        row=tk.Frame(actions,bg=BG);row.pack(fill="x")
        for caption, command in (("QQ 导出中心", self.launch_qq), ("微信 WeChatEXP", self.wechat_dialog), ("其他导入方式", self.import_menu)):
            button(row, caption, command,padx=10,pady=7,bg=PANEL).pack(side="left", padx=(0,7))
        help_label=label(row,"导入帮助 ⓘ",9,MUTED,cursor="question_arrow");help_label.pack(side="right")
        Tooltip(help_label,"支持 JSON / JSONL / CSV / TXT 和 WeChatEXP HTML。\n只提取文字，跳过图片与表情包。\n选择文件后确认会话和哪位是我，再保存档案。导入不调用模型，档案与分析进度保存在本机。")
        columns = tk.PanedWindow(self.page, orient="horizontal", bg=BG, sashwidth=12, bd=0,showhandle=False)
        self.columns=columns
        columns.pack(fill="both", expand=True,pady=(16,0))
        self.contact_card=Card(columns,padding=14)
        self.message_card=Card(columns,padding=14)
        self.character_card=Card(columns,padding=12)
        columns.add(self.contact_card,minsize=168,width=198,stretch='never')
        columns.add(self.message_card,minsize=356,stretch='always')
        columns.add(self.character_card,minsize=174,width=204,stretch='never')
        left,right=self.contact_card.body,self.message_card.body
        character=self.character_card.body
        label(character,"人物档案",13,TEXT,True).pack(anchor="w",pady=(0,12))
        self.character_body=tk.Frame(character,bg=PANEL)
        self.character_body.pack(fill='both',expand=True)
        row=tk.Frame(left,bg=PANEL);row.pack(fill="x")
        label(row, "联系人", 13, TEXT, True).pack(side="left")
        self.profile_count=tk.StringVar(value="0 个档案")
        tk.Label(row,textvariable=self.profile_count,bg=PANEL,fg=MUTED,font=("Microsoft YaHei UI",8)).pack(side="right")
        self.search_var=tk.StringVar()
        label(left,"搜索联系人",9,MUTED).pack(anchor="w",pady=(16,6))
        self.search_entry=tk.Entry(left,textvariable=self.search_var,bg=BG,fg=TEXT,relief="flat",insertbackground=TEAL,highlightthickness=1,highlightbackground=BORDER,highlightcolor=TEAL)
        self.search_entry.pack(fill="x",ipady=7)
        self.list = ContactList(left, bg=PANEL, fg=TEXT, selectbackground=ACCENT_LIGHT, selectforeground=TEAL, relief="flat", bd=0, exportselection=False,activestyle="none",font=("Microsoft YaHei UI",11),highlightthickness=0,height=4)
        self.list.pack(fill="both", expand=True, pady=(14,8))
        self.list.bind("<<ListboxSelect>>", self.selected)
        button(left, "打开存档目录", lambda: os.startfile(str(app.store.directory)),pady=7).pack(fill="x", pady=4)
        self.contact_title=tk.StringVar(value="尚未选择联系人")
        contact_header=tk.Frame(right,bg=PANEL);contact_header.pack(fill="x",pady=(0,4))
        label(contact_header,"消息预览",13,TEXT,True).pack(side="left")
        button(contact_header,"⋯",self.contact_menu,padx=10,pady=3).pack(side="right")
        tk.Label(right,textvariable=self.contact_title,bg=PANEL,fg=TEXT,font=("Microsoft YaHei UI",11,"bold"),anchor="w").pack(fill="x",pady=(5,4))
        self.note = tk.StringVar(value="先选择左侧联系人，或导入一份聊天记录。")
        note_label=tk.Label(right, textvariable=self.note, bg=PANEL, fg=MUTED, anchor="w", font=("Microsoft YaHei UI",8))
        note_label.pack(fill="x", pady=(0, 12))
        Tooltip(note_label,"档案只显示文字。选择时间范围后点击开始评分，十条一组保存；已经处理的消息默认不会重复分析。")
        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True)
        raw_frame, result_frame = tk.Frame(notebook, bg=PANEL), tk.Frame(notebook, bg=PANEL)
        notebook.add(raw_frame, text="聊天与逐条评分")
        notebook.add(result_frame, text="档案分析与回复")
        self.notebook = notebook
        from .history_ui import HistoryPanel
        self.history = HistoryPanel(raw_frame, self,character_parent=self.character_body)
        self.history.pack(fill="both", expand=True)
        self.result = self.scrolled_text(result_frame, readonly=True)
        footer = tk.Frame(result_frame, bg=PANEL)
        footer.pack(fill="x", side="bottom", pady=8)
        self.copy_button=button(footer,"复制推荐回复",self.copy_reply,padx=10,pady=5)
        button(footer, "生成所选范围回复", self.history.summarize, padx=10, pady=5).pack(side="left", padx=5)
        self.analyzed_profile = None
        set_text(self.result, "在聊天页选择时间范围，点击“生成所选范围回复”获得建议。", True)
        self.search_var.trace_add("write",lambda *_:self.refresh())
        self.refresh()
        self.root.after(120, self.poll)

    def popup(self, choices):
        menu=tk.Menu(self.page,tearoff=0)
        for caption,action in choices:
            menu.add_command(label=caption,command=action)
        try:
            menu.tk_popup(self.root.winfo_pointerx(),self.root.winfo_pointery())
        finally:
            menu.grab_release()

    def import_menu(self):
        self.popup((("粘贴文字记录",self.paste),("导入 SQLite 数据库",self.pick_database)))

    def contact_menu(self):
        self.popup((("带档案进入实时分析",self.realtime),("导出当前档案 JSON",self.export)))

    def scrolled_text(self, parent, readonly=False):
        BG, PANEL, TEXT, MUTED, TEAL, label, button, text_box, set_text = self.style
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="both", expand=True)
        box = text_box(frame, readonly=readonly)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=box.yview)
        box.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        box.pack(fill="both", expand=True, side="left")
        return box

    def refresh(self, select_id=None):
        if select_id is None and hasattr(self,'history') and self.history.profile:
            select_id=self.history.profile.id
        profiles=self.app.archives.profiles()
        self.profile_count.set(f"{len(profiles)} 个档案")
        query=self.search_var.get().strip().lower()
        self.profiles = [p for p in profiles if not query or query in p.name.lower()]
        self.list.clear_hover()
        self.list.delete(0, "end")
        for i, profile in enumerate(self.profiles):
            self.list.insert("end", f" {profile.name}  ·  {profile.count} 条")
            if profile.id == select_id:
                self.list.selection_set(i)
                self.list.see(i)
        self.list.refresh_theme()
        if self.list.curselection():
            self.selected()
        elif hasattr(self,'history'):
            self.history.clear_profile()
            self.contact_title.set('尚未选择联系人')
            self.note.set('没有匹配的联系人，请换个关键词。' if query else '先选择左侧联系人，或导入一份聊天记录。')
            self.analyzed_profile=None
            self.copy_button.pack_forget()
            self.style[-1](self.result,'先选择联系人，再筛选时间范围，即可生成回复建议。',True)

    def current_profile(self):
        selected = self.list.curselection()
        if not selected:
            raise ValueError("请先选择一个联系人档案。")
        return self.profiles[selected[0]]

    def selected(self, event=None):
        if not self.list.curselection():
            return
        profile = self.current_profile()
        self.contact_title.set(profile.name)
        self.note.set(f"{profile.platform}  ·  {profile.count} 条文字记录")
        self.history.select_profile(profile)
        if self.analyzed_profile != profile.id:
            self.copy_button.pack_forget()
            self.style[-1](self.result, "选择时间范围后，点击下方“生成所选范围回复”。", True)

    def run(self, operation, callback):
        if self.busy:
            self.app.set_status("正在导入，请等待本次操作完成。")
            return
        self.busy = True
        self.app.set_status("读取本地聊天记录中…")
        def worker():
            try:
                self.queue.put((callback, operation(), None))
            except Exception as error:
                self.queue.put((callback, None, str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        if self.app.closed:
            return
        try:
            callback, result, error = self.queue.get_nowait()
            self.busy = False
            if error:
                self.app.show_error(error)
            else:
                try:
                    callback(result)
                except Exception as failure:
                    self.app.show_error(str(failure))
        except queue.Empty:
            pass
        self.root.after(120, self.poll)

    def pick_file(self):
        path = filedialog.askopenfilename(parent=self.root, title="选择第三方聊天导出文件", filetypes=[("聊天导出文件", "*.json *.jsonl *.ndjson *.csv *.tsv *.txt *.html *.htm"), ("所有文件", "*.*")])
        if path:
            self.run(lambda: load_file(Path(path)), self.preview)

    def dialog(self, title, size="860x670"):
        BG, PANEL = self.style[:2]
        self.app.stop_monitor(show_main=True)
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=PANEL)
        dialog.geometry(size)
        dialog.transient(self.root)
        dialog.grab_set()
        return dialog

    def preview(self, bundle):
        BG, PANEL, TEXT, MUTED, TEAL, label, button, text_box, set_text = self.style
        dialog = self.dialog("导入预览 · 确认会话和发言人")
        label(dialog, "确认后才写入本地档案", 16, TEAL, True).pack(anchor="w", padx=18, pady=(16, 5))
        label(dialog, "只支持两人私聊；检查会话、哪位是我和预览文字。文件中的身份提示仍需你确认。", 9, MUTED, wraplength=815).pack(anchor="w", padx=18, pady=(0, 10))
        conversation_var, self_var, target_var, name_var = (tk.StringVar() for _ in range(4))
        choices = [f"{i + 1}. {c.name} · {len(c.messages)} 条" for i, c in enumerate(bundle.conversations)]
        rows = tk.Frame(dialog, bg=PANEL)
        rows.pack(fill="x", padx=18)
        combos = {}
        for caption, variable, values in (("会话", conversation_var, choices), ("哪位是我", self_var, []), ("保存到", target_var, [])):
            row = tk.Frame(rows, bg=PANEL)
            row.pack(fill="x", pady=4)
            label(row, caption, 9, MUTED, width=10).pack(side="left")
            combo = ttk.Combobox(row, textvariable=variable, values=values, state="readonly")
            combo.pack(fill="x", side="left", expand=True)
            combos[caption] = combo
        row = tk.Frame(rows, bg=PANEL)
        row.pack(fill="x", pady=4)
        label(row, "档案名称", 9, MUTED, width=10).pack(side="left")
        tk.Entry(row, textvariable=name_var, bg=BG, fg=TEXT, insertbackground=TEAL, relief="flat").pack(fill="x", side="left", expand=True, ipady=6)
        info = tk.StringVar()
        tk.Label(dialog, textvariable=info, bg=PANEL, fg=MUTED, anchor="w", wraplength=815).pack(fill="x", padx=18, pady=8)
        preview_frame = tk.Frame(dialog, bg=PANEL)
        preview_frame.pack(fill="both", expand=True, padx=18)
        box = self.scrolled_text(preview_frame, True)
        destinations = []
        def current():
            return bundle.conversations[choices.index(conversation_var.get())]
        def identity_changed(event=None):
            nonlocal destinations
            c = current()
            destinations = [p for p in self.app.archives.profiles() if p.conversation_key == c.key and p.self_identity == self_var.get() and p.platform == c.platform]
            combos["保存到"].configure(values=["新建联系人档案"] + [f"追加：{p.name}（{p.count} 条）" for p in destinations])
            target_var.set("新建联系人档案" if not destinations else f"追加：{destinations[0].name}（{destinations[0].count} 条）")
            info.set(("群聊无法用于双方分析。" if c.is_group else f"{c.platform} · 全部 {len(c.messages)} 条文本，预览最后 100 条。") + " " + " ".join(bundle.warnings))
            set_text(box, "\n\n".join(f"{m.timestamp}  {'我' if m.sender == self_var.get() else '对方'}（{m.display_name or m.sender} / {m.sender}）：{m.text}" for m in c.messages[-100:]), True)
        def changed(event=None):
            c = current()
            identities = c.identities()
            combos["哪位是我"].configure(values=identities)
            self_var.set(c.owner if c.owner in identities else "")
            name_var.set(c.name)
            identity_changed()
        conversation_var.set(choices[0])
        combos["会话"].bind("<<ComboboxSelected>>", changed)
        combos["哪位是我"].bind("<<ComboboxSelected>>", identity_changed)
        changed()
        def commit():
            try:
                c = current()
                messages = c.choose_self(self_var.get())
                index = combos["保存到"].current()
                name = name_var.get().strip()
                if index == 0 and not name:
                    raise ValueError("请填写联系人档案名称。")
                profile = self.app.archives.create(name, c.platform, c.key, self_var.get()) if index == 0 else destinations[index - 1]
                added = self.app.archives.import_messages(profile.id, messages)
                dialog.destroy()
                self.search_var.set("")
                self.refresh(profile.id)
                self.app.activate_profile(profile.id)
                self.app.set_status(f"已保存 {profile.name}：新增 {added} 条，跳过 {len(messages) - added} 条已有消息。可分析档案，或带历史进入实时模式。")
            except Exception as error:
                messagebox.showerror("导入未完成", str(error), parent=dialog)
        footer = tk.Frame(dialog, bg=PANEL)
        footer.pack(fill="x", padx=18, pady=12)
        button(footer, "确认身份并保存档案", commit, True).pack(side="right")
        button(footer, "取消", dialog.destroy).pack(side="right", padx=8)
        label(footer, "档案存于本机；点击分析时才发送历史摘录至所选 API。", 8, MUTED, wraplength=440).pack(side="left")
        self.app.set_status("已读取导出文件，请在预览中确认身份与会话。")

    def paste(self):
        BG, PANEL, TEXT, MUTED, TEAL, label, button, text_box, set_text = self.style
        dialog = self.dialog("粘贴聊天记录")
        label(dialog, "支持 昵称：内容、QQ 时间+昵称、微信昵称+时间格式。", 10, MUTED).pack(padx=18, pady=16, anchor="w")
        box = self.scrolled_text(dialog)
        def read():
            try:
                bundle = from_text(box.get("1.0", "end-1c"))
                dialog.destroy()
                self.preview(bundle)
            except Exception as error:
                messagebox.showerror("无法解析", str(error), parent=dialog)
        button(dialog, "预览并选择身份", read, True).pack(anchor="e", padx=18, pady=12)

    def pick_database(self):
        path = filedialog.askopenfilename(parent=self.root, title="选择已解密的 SQLite 聊天数据库", filetypes=[("SQLite 数据库", "*.db *.sqlite *.sqlite3"), ("所有文件", "*.*")])
        if path:
            self.run(lambda: (Path(path), sqlite_tables(Path(path))), self.database_dialog)

    def database_dialog(self, result):
        path, schema = result
        if not schema:
            raise ValueError("该数据库没有可读取的消息表。")
        BG, PANEL, TEXT, MUTED, TEAL, label, button, text_box, set_text = self.style
        dialog = self.dialog("SQLite 导入 · 只读访问", "750x620")
        label(dialog, "选择消息表与字段", 17, TEAL, True).pack(anchor="w", padx=18, pady=15)
        label(dialog, "数据库只读。微信 3.x 的 MSG 表会自动匹配；其他明文数据库请按列名选择。", 9, MUTED, wraplength=700).pack(anchor="w", padx=18)
        body = tk.Frame(dialog, bg=PANEL)
        body.pack(fill="x", padx=18, pady=10)
        table_var = tk.StringVar(value=next((t for t, cols in schema.items() if guess_columns(cols).get("text")), next(iter(schema))))
        table = ttk.Combobox(body, textvariable=table_var, values=list(schema), state="readonly")
        table.pack(fill="x", pady=(0, 12))
        fields, combos = {}, {}
        for key, caption in (("text", "消息内容（必选）"), ("sender", "发言人 ID / 昵称"), ("self", "是否自己（0/1）"), ("time", "发送时间"), ("conversation", "会话 / 联系人 ID"), ("id", "消息 ID"), ("type", "消息类型")):
            row = tk.Frame(body, bg=PANEL)
            row.pack(fill="x", pady=4)
            label(row, caption, 9, MUTED, width=22).pack(side="left")
            fields[key] = tk.StringVar()
            combos[key] = ttk.Combobox(row, textvariable=fields[key], state="readonly")
            combos[key].pack(side="left", fill="x", expand=True)
        filter_var = tk.StringVar()
        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x", pady=10)
        label(row, "只导入类型值（空=全部）", 9, MUTED, width=22).pack(side="left")
        tk.Entry(row, textvariable=filter_var, bg=BG, fg=TEXT, insertbackground=TEAL, relief="flat").pack(side="left", fill="x", expand=True, ipady=6)
        def change(event=None):
            columns = schema[table_var.get()]
            guessed = guess_columns(columns)
            for key in fields:
                combos[key].configure(values=[""] + columns)
                fields[key].set(guessed[key])
            filter_var.set("1" if table_var.get().lower() == "msg" and guessed["type"] else "")
        table.bind("<<ComboboxSelected>>", change)
        change()
        label(dialog, "发言人或是否自己至少选一个；群聊会在会话预览中被排除。\n若原库仍加密，请使用上方微信 / QQ 导出入口。", 9, MUTED, wraplength=700).pack(anchor="w", padx=18, pady=12)
        def read():
            mapping, selected, text_type = {k: v.get() for k, v in fields.items()}, table_var.get(), filter_var.get().strip()
            dialog.destroy()
            self.run(lambda: load_sqlite(path, selected, mapping, text_type), self.preview)
        button(dialog, "只读加载并预览", read, True).pack(anchor="e", padx=18, pady=12)

    def weflow_dialog(self):
        BG, PANEL, TEXT, MUTED, TEAL, label, button, text_box, set_text = self.style
        dialog = self.dialog("微信 WeFlow 本地 API", "790x610")
        label(dialog, "从本机 WeFlow 导入微信历史", 16, TEAL, True).pack(anchor="w", padx=18, pady=16)
        label(dialog, "先在 WeFlow 中配置微信数据库并启用“API 服务”，再填写地址与令牌。\n此入口调用公开的本地 API；也可直接导入 WeFlow 导出的 JSON / CSV / TXT。", 9, MUTED, wraplength=745).pack(anchor="w", padx=18)
        variables = [tk.StringVar(value="http://127.0.0.1:5031"), tk.StringVar()]
        for i, caption in enumerate(("本地 API 地址", "访问令牌（如已设置）")):
            row = tk.Frame(dialog, bg=PANEL)
            row.pack(fill="x", padx=18, pady=7)
            label(row, caption, 9, MUTED, width=23).pack(side="left")
            tk.Entry(row, textvariable=variables[i], show="●" if i else "", bg=BG, fg=TEXT, insertbackground=TEAL, relief="flat").pack(fill="x", expand=True, side="left", ipady=6)
        sessions = []
        listbox = tk.Listbox(dialog, bg=BG, fg=TEXT, selectbackground="#32556A", exportselection=False, relief="flat")
        listbox.pack(fill="both", expand=True, padx=18, pady=10)
        def loaded(rows):
            if not dialog.winfo_exists():
                return
            sessions[:] = rows
            listbox.delete(0, "end")
            for row in rows:
                listbox.insert("end", f"{row.get('displayName') or row.get('username')}  /  {row.get('username')}")
            self.app.set_status(f"WeFlow 返回 {len(rows)} 个私聊会话，选择一个后导入。")
        def connect():
            try:
                client = WeFlowClient(variables[0].get(), variables[1].get())
                self.run(client.sessions, loaded)
            except Exception as error:
                messagebox.showerror("WeFlow", str(error), parent=dialog)
        def read():
            try:
                if not listbox.curselection():
                    raise ValueError("请先连接并选择一个私聊会话。")
                row = sessions[listbox.curselection()[0]]
                client = WeFlowClient(variables[0].get(), variables[1].get())
                dialog.destroy()
                self.run(lambda: client.history(str(row["username"]), str(row.get("displayName") or row["username"])), self.preview)
            except Exception as error:
                self.app.show_error(str(error))
        footer = tk.Frame(dialog, bg=PANEL)
        footer.pack(fill="x", padx=18, pady=12)
        button(footer, "WeFlow 项目 / 配置说明", lambda: webbrowser.open("https://github.com/hicccc77/WeFlow"), padx=10).pack(side="left")
        button(footer, "连接并列出私聊", connect).pack(side="left", padx=8)
        button(footer, "导入所选会话", read, True).pack(side="right")

    def launch_qq(self):
        from .qq_ui import QQExportDialog
        QQExportDialog(self)
        self.app.set_status("QQ 导出中心已打开：选择联系人、读取历史，再导出 JSON 或导入存档。")

    def wechat_dialog(self):
        from .wechat_ui import wechat_dialog
        wechat_dialog(self)

    def analyze_selected(self):
        self.history.start()

    def show_result(self, result, profile_id):
        if not profile_id:
            return
        self.analyzed_profile = profile_id
        try:
            if self.current_profile().id != profile_id:
                return
        except ValueError:
            return
        lines = [result.source, "", "当前语境", result.summary, "", "我方逻辑", result.self_logic, "", "对方逻辑", result.other_logic, "", "下一句回复建议"]
        for i, reply in enumerate(result.replies):
            lines.extend(["", f"{i + 1}. {reply['style']}", reply["text"], "理由：" + reply["reason"]])
        lines.extend(["", "互动积极度：" + str(result.signal_score), "只衡量文字中的互动线索，不代表真实好感。", "", *result.cautions])
        self.style[-1](self.result, "\n".join(lines), True)
        if result.replies:self.copy_button.pack(side="left")
        else:self.copy_button.pack_forget()

    def copy_reply(self):
        try:
            profile = self.current_profile()
            if self.analyzed_profile != profile.id or self.app.active_profile != profile.id or not self.app.result or not self.app.result.replies:
                raise ValueError("请先分析当前选中的档案。")
            self.app.copy(self.app.result.replies[0]["text"])
        except Exception as error:
            self.app.show_error(str(error))

    def realtime(self):
        try:
            profile = self.current_profile()
            self.history.pause()
            self.app.activate_profile(profile.id)
            self.app.show_page("实时分析")
            self.app.set_status(f"已关联 {profile.name} 的历史档案。请打开同一人的聊天并框选；切换联系人前先更换档案。")
        except Exception as error:
            self.app.show_error(str(error))

    def export(self):
        try:
            profile = self.current_profile()
            path = filedialog.asksaveasfilename(parent=self.root, title="导出联系人档案", defaultextension=".json", initialfile="聊天档案.json", filetypes=[("ChatLab JSON", "*.json")])
            if path:
                self.app.archives.export_chatlab(profile.id, Path(path))
                self.app.set_status("档案已导出为 ChatLab JSON，可再次导入或用于其他工具。")
        except Exception as error:
            self.app.show_error(str(error))
