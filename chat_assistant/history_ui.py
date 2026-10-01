"""Range selection and restartable archive analysis; Tk stays on the main thread."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from dataclasses import replace
from datetime import datetime, timezone, timedelta

from .archives import latest_window
from .chat_view import CharacterPanel, ChatBubbleView, ProgressBall
from .core import Transcript
from .history_analysis import ProgressStats, time_bounds
from .history_runner import run_history
from .batch_analysis import explain_messages
from .ui_fonts import ui_font
from .date_picker import DateField
from . import date_picker
from .ui_widgets import Tooltip


class HistoryPanel(tk.Frame):
    PAGE_SIZE = 80

    def __init__(self, parent, center, character_parent=None):
        from .app import BG, PANEL, TEXT, MUTED, TEAL, button
        super().__init__(parent, bg=PANEL)
        self.center, self.app = center, center.app
        self.profile = None
        self.entries, self.entry_map = [], {}
        self.positions={};self.issue_counts={};self.handled_count=0
        self.stats = ProgressStats([])
        self.page_index = 0
        self.busy = False
        self.cancel = threading.Event()
        self.events = queue.Queue()
        self.job_profile = None
        self.selected_ids=set()
        self.start_var, self.end_var = tk.StringVar(), tk.StringVar()
        self.force_var = tk.BooleanVar(value=False)
        self.job_note = tk.StringVar(value="每10条保存 · 支持断点继续")
        self.page_note = tk.StringVar(value="尚未选择档案")
        self.issue_note = tk.StringVar()
        top=tk.Frame(self,bg=PANEL);top.pack(fill='x',pady=(12,6))
        tk.Label(top,text='时间范围',bg=PANEL,fg=TEXT,font=ui_font(self,9,True)).pack(side='left')
        help_label=tk.Label(top,text='ⓘ',bg=PANEL,fg=MUTED,font=ui_font(self,10),cursor='question_arrow')
        help_label.pack(side='left',padx=5)
        self.range_tooltip=Tooltip(help_label,"点击日期打开日历；今日和近7天按北京时间计算，结束日期包含当天。\n不限制日期时，也包含时间未知的消息。\n需要精确时间可在日历勾选“精确到时间”。\n选择后点筛选；重置恢复全部时间。")
        for caption,key in reversed((('今日','today'),('近7天','week'),('全部时间','all'))):
            button(top,caption,lambda k=key:self.quick_range(k),padx=7,pady=4,font=ui_font(self,8),bg=PANEL).pack(side='right',padx=(4,0))
        row = tk.Frame(self, bg=PANEL)
        self.range_row = row
        row.pack(fill="x", pady=(9, 5))
        self.start_picker=DateField(row,self.start_var,'开始日期',validator=lambda value:time_bounds(value,self.end_var.get()),on_change=self.range_changed)
        self.start_picker.pack(side='left')
        tk.Label(row,text='—',bg=PANEL,fg=MUTED,font=ui_font(self,9)).pack(side='left',padx=5)
        self.end_picker=DateField(row,self.end_var,'结束日期',validator=lambda value:time_bounds(self.start_var.get(),value),on_change=self.range_changed)
        self.end_picker.pack(side='left')
        self.filter_button=button(row,'筛选',self.apply_range,padx=7,pady=6,font=ui_font(self,9),bg=PANEL)
        self.filter_button.pack(side='left',padx=(7,2))
        self.reset_button=button(row,'重置',self.reset_range,padx=5,pady=6,font=ui_font(self,9),bg=PANEL)
        self.reset_button.pack(side='left')
        actions = tk.Frame(self, bg=PANEL)
        actions.pack(fill="x", pady=7)
        self.start_button = button(actions, "开始评分", self.start, True, padx=10, pady=5)
        self.start_button.pack(side="left")
        self.pause_button = button(actions, "暂停", self.pause, padx=9, pady=5)
        self.pause_button.pack(side="left", padx=5)
        self.resume_button = button(actions, "继续上次任务", self.resume, padx=10, pady=5)
        self.resume_button.pack(side="left")
        self.more_button=button(actions,"分析选项",self.analysis_menu,padx=9,pady=5)
        self.more_button.pack(side="right")
        self.explain_button=button(actions,"解释所选",self.explain_selected,padx=9,pady=5)
        self.clear_selection_button=button(actions,"取消选择",self.clear_selection,padx=8,pady=5)
        status=tk.Frame(self,bg=PANEL);status.pack(fill='x',pady=(0,10))
        note_label=tk.Label(status,textvariable=self.job_note,bg=PANEL,fg=MUTED,font=ui_font(self,8),anchor='w')
        note_label.pack(side='left')
        Tooltip(note_label,"每十条一组请求和保存，最后不足十条也保存。无法判断的消息会自动继续，仅提醒页码。\n点击气泡多选、右键解释单条；解释由DeepSeek按需完成，不改变Jev评分。\n未完成任务可以暂停或退出，下次继续上次任务。")
        self.issue_label=tk.Label(self,textvariable=self.issue_note,bg="#FFF3DA",fg="#875C14",font=ui_font(self,9),anchor="w",cursor="hand2",wraplength=760,padx=7,pady=4)
        self.issue_label.bind("<Button-1>",lambda e:self.jump_issue())
        pager = tk.Frame(self, bg="#F4F3F8")
        pager.pack(fill="x", side="bottom")
        button(pager, "上一页", lambda:self.turn_page(-1), padx=8, pady=4).pack(side="left")
        tk.Label(pager, textvariable=self.page_note, bg="#F4F3F8", fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(side="left", padx=8)
        button(pager, "下一页", lambda:self.turn_page(1), padx=8, pady=4).pack(side="right")
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.character = CharacterPanel(character_parent or self.body)
        self.character.pack(fill='both',expand=True)
        self.chat = ChatBubbleView(self.body)
        self.chat.on_select=self.toggle_selection
        self.chat.on_explain=lambda entry_id:self.explain_selected([entry_id])
        self.chat.pack(side="left", fill="both", expand=True)
        self.ball = ProgressBall(character_parent or self.body)
        Tooltip(self.ball.canvas,"攻略进度来自已分析文字的互动信号，不代表真实喜欢的概率。可按住拖动；点击人物档案查看各维度。")
        self.update_buttons()
        self.app.root.after(100, self.poll)

    def select_profile(self, profile):
        changed = self.profile is None or self.profile.id != profile.id
        if changed and self.busy:
            self.pause()
        self.profile = profile
        if changed:
            self.selected_ids.clear()
            self.start_var.set(""); self.end_var.set(""); self.force_var.set(False)
            previous = self.app.archives.last_run(profile.id)
            if previous and previous["state"] != "completed":
                self.start_var.set(previous["start_text"]); self.end_var.set(previous["end_text"])
        self.apply_range()

    def all_time(self):
        self.start_var.set(""); self.end_var.set("")
        self.apply_range()

    def quick_range(self,key):
        today=date_picker.beijing_today()
        if key=='all':start=end=''
        elif key in ('today','week'):
            start=(today-timedelta(days=6 if key=='week' else 0)).isoformat();end=today.isoformat()
        else:raise ValueError('Unknown quick range')
        self.start_var.set(start);self.end_var.set(end);self.apply_range()

    def reset_range(self):
        self.quick_range('all')

    def range_changed(self):
        self.job_note.set('日期已更改 · 点击筛选')

    def clear_profile(self):
        self.profile=None
        self.entries=[];self.entry_map={};self.positions={};self.issue_counts={};self.handled_count=0
        self.stats=ProgressStats([]);self.selected_ids.clear()
        self.start_var.set('');self.end_var.set('')
        self.render(reset=True);self.update_buttons()

    def apply_range(self):
        try:
            if not self.profile:
                return
            bounds = time_bounds(self.start_var.get(), self.end_var.get())
            self.entries = self.app.archives.entries(self.profile.id, *bounds)
            self.entry_map = {e.id:e for e in self.entries}
            self.positions={e.id:i for i,e in enumerate(self.entries)}
            self.issue_counts={}
            self.handled_count=sum(e.done for e in self.entries)
            for i,e in enumerate(self.entries):
                if e.issue:
                    page=i//self.PAGE_SIZE+1
                    self.issue_counts[page]=self.issue_counts.get(page,0)+1
            self.selected_ids.intersection_update(self.entry_map)
            self.stats = ProgressStats(self.entries)
            self.page_index = 0
            self.render(reset=True)
            self.update_buttons()
        except Exception as error:
            self.app.show_error(str(error))

    def render(self, reset=False):
        pages = max(1, (len(self.entries)+self.PAGE_SIZE-1)//self.PAGE_SIZE)
        self.page_index = max(0, min(self.page_index, pages-1))
        offset = self.page_index*self.PAGE_SIZE
        name = self.profile.name if self.profile else "对话人物"
        self.chat.selected_ids=self.selected_ids
        self.chat.empty_state='请先选择联系人' if not self.profile else '这个时间范围没有消息'
        self.chat.empty_hint='选择左侧联系人查看对话，或点击上方导入记录。' if not self.profile else '试试“全部时间”，或重新选择日期范围。'
        self.chat.render(self.entries[offset:offset+self.PAGE_SIZE], name, reset)
        summary = self.stats.summary()
        self.character.update_progress(name, summary,has_profile=bool(self.profile))
        self.ball.render(summary["score"])
        self.page_note.set(f"{self.page_index+1} / {pages} 页 · {len(self.entries)} 条" if self.profile else '等待选择联系人')
        self.issue_pages=sorted(self.issue_counts)
        if self.issue_pages:
            page_text="、".join(str(p) for p in self.issue_pages[:12])
            extra="等" if len(self.issue_pages)>12 else ""
            self.issue_note.set(f"无法判断：第 {page_text} 页{extra} · 已自动继续，点击查看")
            self.issue_label.pack(fill="x",before=self.body,pady=(0,6))
        else:
            self.issue_note.set("");self.issue_label.pack_forget()
        self.update_selection()

    def jump_issue(self):
        if self.issue_pages:
            next_page=next((p for p in self.issue_pages if p>self.page_index+1),self.issue_pages[0])
            self.page_index=next_page-1
            self.render(reset=True)

    def toggle_selection(self,entry_id):
        if entry_id in self.selected_ids:self.selected_ids.remove(entry_id)
        else:self.selected_ids.add(entry_id)
        self.render()

    def clear_selection(self):
        self.selected_ids.clear();self.render()

    def update_selection(self):
        if self.selected_ids:
            self.explain_button.configure(text=f"解释所选 {len(self.selected_ids)} 条",state="disabled" if self.busy else "normal")
            self.explain_button.pack(side="left",padx=5)
            self.clear_selection_button.pack(side="left")
        else:
            self.explain_button.pack_forget();self.clear_selection_button.pack_forget()

    def analysis_menu(self):
        menu=tk.Menu(self,tearoff=0)
        menu.add_checkbutton(label="重新评分已完成记录",variable=self.force_var)
        menu.add_command(label="选择本页消息",command=self.select_page)
        menu.add_command(label="模型与字体设置",command=lambda:self.app.show_page("设置"))
        try:menu.tk_popup(self.winfo_pointerx(),self.winfo_pointery())
        finally:menu.grab_release()

    def select_page(self):
        offset=self.page_index*self.PAGE_SIZE
        self.selected_ids.update(e.id for e in self.entries[offset:offset+self.PAGE_SIZE])
        self.render()

    def turn_page(self, step):
        self.page_index += step
        self.render(reset=True)

    def update_buttons(self):
        self.start_button.configure(state="disabled" if self.busy or not self.profile else "normal")
        self.pause_button.configure(state="normal" if self.busy else "disabled")
        if self.busy:self.pause_button.pack(side="left",padx=5)
        else:self.pause_button.pack_forget()
        previous = self.app.archives.last_run(self.profile.id) if self.profile else None
        resumable = previous and previous["state"] != "completed"
        self.resume_button.configure(state="normal" if resumable and not self.busy else "disabled")
        if resumable and not self.busy:self.resume_button.pack(side="left",padx=5)
        else:self.resume_button.pack_forget()
        self.more_button.configure(state="disabled" if self.busy else "normal")
        if not self.busy and previous and previous["state"] != "completed":
            self.job_note.set(f"已保存 {previous['completed']}/{previous['total']} 条 · 可继续")
        elif not self.busy:
            self.job_note.set("每10条保存 · 支持断点继续")
        self.update_selection()

    def launch(self, run_id=None):
        try:
            if self.busy:
                self.app.set_status("当前逐条分析尚未结束，可先暂停。")
                return
            profile = self.center.current_profile()
            if self.app.analysis_job:
                raise ValueError("另一条模型请求仍在处理，请等它完成再开始逐条分析。")
            settings = self.app.saved_settings()
            (replace(settings,mode="TypeSafe Jev") if settings.mode!="DeepSeek" else settings).validate()
            start_text, end_text = self.start_var.get().strip(), self.end_var.get().strip()
            entries = None
            if run_id:
                info = self.app.archives.run_info(run_id)
                start_text, end_text = info["start_text"], info["end_text"]
                self.start_var.set(start_text); self.end_var.set(end_text)
            else:
                entries = self.app.archives.entries(profile.id, *time_bounds(start_text, end_text))
                if not entries:
                    raise ValueError("这个时间范围没有文字消息；时间未知的消息只在不限时间时包含。")
            self.app.stop_monitor(show_main=True)
            self.app.activate_profile(profile.id)
            self.app.settings = settings
            self.busy, self.job_profile = True, profile.id
            self.cancel = threading.Event()
            self.job_note.set("正在评分，每10条一组保存到本机…")
            self.update_buttons()
            self.center.notebook.select(0)
            self.apply_range()
            force, cancel = self.force_var.get(), self.cancel
            def worker():
                try:
                    result = run_history(self.app.archives, settings, profile.id, entries, start_text, end_text, force,
                                         run_id, cancel, lambda kind,data:self.events.put((kind,data)))
                    self.events.put(("finished", result))
                except Exception as error:
                    self.events.put(("error", str(error)))
            threading.Thread(target=worker, daemon=True).start()
        except Exception as error:
            self.app.show_error(str(error))

    def start(self):
        self.launch()

    def resume(self):
        try:
            profile = self.center.current_profile()
            previous = self.app.archives.last_run(profile.id)
            if not previous or previous["state"] == "completed":
                raise ValueError("当前联系人没有未完成任务。")
            self.launch(previous["id"])
        except Exception as error:
            self.app.show_error(str(error))

    def pause(self):
        if self.busy:
            self.cancel.set()
            self.job_note.set("正在暂停：当前一组返回后保存，再停止后续请求。")

    def poll(self):
        if self.app.closed:
            return
        try:
            while True:
                kind, data = self.events.get_nowait()
                visible = self.profile and self.profile.id == self.job_profile
                if kind in {"started", "rated", "batch"}:
                    if visible:
                        self.job_note.set(f"已保存 {data['completed']}/{data['total']} 条 · 每10条一组")
                        if kind in {"rated","batch"}:
                            for row in data["results"]:
                                if row["entry_id"] not in self.entry_map:continue
                                entry = self.entry_map[row["entry_id"]]
                                page=self.positions[entry.id]//self.PAGE_SIZE+1
                                change=int(bool(row.get("issue")))-int(bool(entry.issue))
                                count=self.issue_counts.get(page,0)+change
                                if count:self.issue_counts[page]=count
                                else:self.issue_counts.pop(page,None)
                                if not entry.done:self.handled_count+=1
                                if row["rating"]:
                                    entry.rating={**row["rating"],"analyzed_at":datetime.now(timezone.utc).isoformat()}
                                entry.issue=row.get("issue");entry.explanation=None;entry.done=True
                                self.stats.update(entry)
                            self.render()
                elif kind=="explained":
                    if visible:
                        for row in data:
                            if row["entry_id"] in self.entry_map:self.entry_map[row["entry_id"]].explanation=row
                        self.job_explanations.update({r["entry_id"]:r for r in data})
                        self.show_explanations(list(self.job_explanations.values()))
                        self.render()
                elif kind in {"finished", "error"}:
                    self.busy = False
                    self.update_buttons()
                    if kind == "error":
                        self.app.show_error(data + " 已完成条目保留，可点击继续上次任务。")
                    else:
                        self.app.set_status(f"{'已暂停' if data['state']=='paused' else '分析完成'}：已保存 {data['completed']}/{data['total']} 条。")
                        if visible:
                            self.job_note.set(f"{'任务已暂停，可继续' if data['state']=='paused' else '本次任务完成'} · 已保存 {data['completed']}/{data['total']} 条")
        except queue.Empty:
            pass
        self.app.root.after(100, self.poll)

    def summarize(self):
        try:
            if self.busy:
                raise ValueError("请先暂停逐条分析，待当前条保存后再生成回复建议。")
            profile = self.center.current_profile()
            self.select_profile(profile)
            if not self.entries:
                raise ValueError("所选范围没有文字记录。")
            transcript = Transcript(latest_window([e.message for e in self.entries]), "所选时间范围 · 回复建议")
            self.app.activate_profile(profile.id)
            self.app.settings = self.app.saved_settings()
            self.app.settings.validate()
            self.app.transcript = transcript
            self.center.style[-1](self.app.editor, transcript.text)
            self.center.analyzed_profile = None
            self.center.style[-1](self.center.result, "正在根据所选范围的最近文字生成建议…", True)
            self.center.notebook.select(1)
            self.app.submit_analysis(transcript, None, use_archive_context=False)
        except Exception as error:
            self.app.show_error(str(error))

    def show_explanations(self,rows):
        self.center.analyzed_profile=None
        self.center.copy_button.pack_forget()
        pieces=[]
        for row in sorted(rows,key=lambda r:self.positions.get(r["entry_id"],0)):
            entry=self.entry_map.get(row["entry_id"])
            if entry:pieces.append(f"{entry.message.speaker}：{entry.message.text}\n\n{row['text']}\n")
        self.center.style[-1](self.center.result,"按需文字解释 · 已有评分保持不变\n\n"+"\n────────\n\n".join(pieces),True)
        self.center.notebook.select(1)

    def explain_selected(self,identities=None):
        try:
            if self.busy or self.app.analysis_job:raise ValueError("请等待当前请求完成后再解释消息。")
            ids=set(identities if identities is not None else self.selected_ids)
            positions=[i for i,e in enumerate(self.entries) if e.id in ids]
            if not positions:raise ValueError("点击气泡选择消息，或右键解释单条。")
            self.job_explanations={self.entries[i].id:{"entry_id":self.entries[i].id,**self.entries[i].explanation} for i in positions if self.entries[i].explanation}
            pending=[i for i in positions if not self.entries[i].explanation]
            if not pending:
                self.show_explanations([{"entry_id":self.entries[i].id,**self.entries[i].explanation} for i in positions]);return
            settings=replace(self.app.saved_settings(),mode="DeepSeek",vision=False);settings.validate()
            self.app.stop_monitor(show_main=True)
            self.job_profile=self.profile.id;self.busy=True;self.cancel=threading.Event()
            self.update_buttons();self.job_note.set("DeepSeek 正在解释所选消息，评分保留…")
            entries=list(self.entries);profile_id=self.profile.id;cancel=self.cancel
            def worker():
                completed=0
                try:
                    for offset in range(0,len(pending),10):
                        if cancel.is_set():break
                        rows=explain_messages(settings,entries,pending[offset:offset+10])
                        self.app.archives.save_explanations(profile_id,rows)
                        completed+=len(rows);self.events.put(("explained",rows))
                    self.events.put(("finished",{"state":"paused" if cancel.is_set() else "completed","completed":completed,"total":len(pending)}))
                except Exception as error:self.events.put(("error",str(error)))
            threading.Thread(target=worker,daemon=True).start()
        except Exception as error:self.app.show_error(str(error))
