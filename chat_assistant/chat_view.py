"""WeChat-like text bubbles and an app-local, draggable progress orb."""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont, ttk

from .analysis import DIMENSIONS
from .history_analysis import display_time, rating_label
from .ui_fonts import ui_font
from .ui_themes import theme_canvas

CHAT_BG = "#EEF2F5"
GREEN = "#95EC69"
INK = "#24304A"
PURPLE = "#7157DA"


def rounded(canvas, x1, y1, x2, y2, fill, radius=6, stroke=None, **options):
    r = min(radius, (x2-x1)/2, (y2-y1)/2)
    points = [x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1]
    return canvas.create_polygon(points, smooth=False, fill=fill, outline=stroke or fill, **options)


class ChatBubbleView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=CHAT_BG,highlightthickness=1,highlightbackground="#C3CDD7")
        self.canvas = tk.Canvas(self, bg=CHAT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.font = ui_font(self,11,role="chat")
        self.entries, self.name = [], "对方"
        self.empty_state='请先选择联系人'
        self.empty_hint='选择左侧联系人查看对话，或点击上方导入记录。'
        self.selected_ids=set()
        self.on_select=self.on_explain=None
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-int(e.delta/120), "units"))
        self.canvas.bind("<Button-3>", self.context_menu)
        self.canvas.bind("<Double-Button-1>", self.context_menu)
        self.canvas.bind("<Button-1>", self.select_message)

    def render(self, entries, name, reset=False):
        self.entries, self.name = entries, name
        self.draw()
        if reset:
            self.canvas.yview_moveto(0)

    def draw(self):
        position = self.canvas.yview()[0]
        self.canvas.delete("all")
        width = max(260, self.canvas.winfo_width())
        y = 18
        if not self.entries:
            middle=width/2;top=max(45,min(90,self.canvas.winfo_height()/3-26))
            self.canvas.create_oval(middle-24,top-24,middle+24,top+24,fill='#EBE8FC',outline='')
            self.canvas.create_rectangle(middle-11,top-7,middle+11,top+7,fill='#6658D9',outline='')
            self.canvas.create_polygon(middle-8,top+6,middle-8,top+12,middle,top+6,fill='#6658D9',outline='')
            self.canvas.create_text(middle,top+49,text=self.empty_state,fill=INK,font=ui_font(self,12,True))
            self.canvas.create_text(middle,top+79,text=self.empty_hint,width=max(150,width-45),fill='#586880',font=ui_font(self,9),justify='center')
        for entry in self.entries:
            message = entry.message
            own = message.speaker == "我"
            tag = "message:" + str(entry.id)
            self.canvas.create_text(width/2, y, text=display_time(message.timestamp), fill="#667789", font=ui_font(self,8))
            y += 22
            maximum = max(120, int(width*.73)-56)
            longest = max((self.font.measure(line) for line in message.text.splitlines()), default=90)
            bubble_width = min(maximum, max(64, longest+28))
            right_edge = width-60 if own else 60+bubble_width
            left_edge = right_edge-bubble_width
            text = self.canvas.create_text(left_edge+14, y+11, anchor="nw", width=bubble_width-28, text=message.text,
                                           fill="#17211B", font=self.font, tags=(tag,))
            bounds = self.canvas.bbox(text)
            bottom = bounds[3]+12
            body = rounded(self.canvas, left_edge, y, right_edge, bottom, GREEN if own else "white",stroke=PURPLE if entry.id in self.selected_ids else "#77BC55" if own else "#CAD3DC",width=2 if entry.id in self.selected_ids else 1,tags=(tag,))
            self.canvas.tag_lower(body, text)
            avatar_x = width-43 if own else 27
            rounded(self.canvas, avatar_x-17, y, avatar_x+17, y+34, "#CEC4F5" if own else "#FFD9AD", radius=7, tags=(tag,))
            self.canvas.create_text(avatar_x, y+17, text="我" if own else self.name[:1] or "对", fill=INK, font=ui_font(self,11,True), tags=(tag,))
            self.canvas.create_polygon(right_edge, y+12, right_edge+7, y+17, right_edge, y+22, fill=GREEN, outline=GREEN) if own else self.canvas.create_polygon(left_edge, y+12, left_edge-7, y+17, left_edge, y+22, fill="white", outline="white")
            y = bottom+7
            if entry.issue or entry.rating:
                caption = "⚠ 无法判断 · 已继续" if entry.issue else "✓ 已分析  ·  " + rating_label(entry.rating)
                stamp = self.canvas.create_text(right_edge if own else left_edge, y, anchor="ne" if own else "nw", width=bubble_width,
                                                text=caption, fill="#875C14" if entry.issue else PURPLE if own else "#267743", font=ui_font(self,10,True), tags=(tag,))
                y = self.canvas.bbox(stamp)[3]+5
                if entry.rating and not entry.issue and entry.rating.get("reason") and not entry.rating.get("source","").startswith("TypeSafe Jev"):
                    reason = self.canvas.create_text(left_edge, y, anchor="nw", width=bubble_width, text=entry.rating["reason"], fill="#536279", font=ui_font(self,8), tags=(tag,))
                    y = self.canvas.bbox(reason)[3]+4
            y += 20
        self.canvas.configure(scrollregion=(0, 0, width, max(y, self.canvas.winfo_height())))
        self.canvas.yview_moveto(position)
        theme_canvas(self.canvas)

    def entry_at(self,event):
        items = self.canvas.find_overlapping(event.x, self.canvas.canvasy(event.y), event.x, self.canvas.canvasy(event.y))
        identity = next((int(t.split(":")[1]) for item in items for t in self.canvas.gettags(item) if t.startswith("message:")), None)
        return next((e for e in self.entries if e.id == identity), None)

    def select_message(self,event):
        entry=self.entry_at(event)
        if entry and self.on_select:self.on_select(entry.id)

    def context_menu(self, event):
        entry=self.entry_at(event)
        if not entry:
            return
        menu = tk.Menu(self, tearoff=0)
        def copy():
            self.clipboard_clear(); self.clipboard_append(entry.message.text)
        menu.add_command(label="复制这条文字", command=copy)
        if self.on_select:menu.add_command(label="取消选择" if entry.id in self.selected_ids else "加入多选",command=lambda:self.on_select(entry.id))
        if self.on_explain:menu.add_command(label="查看已保存解释" if entry.explanation else "DeepSeek 解释这一条",command=lambda:self.on_explain(entry.id))
        if entry.rating:
            def detail():
                from tkinter import messagebox
                r = entry.rating
                messagebox.showinfo("单条分析", rating_label(r)+"\n\n"+r["reason"]+"\n\n来源："+r["source"]+"\n分析时间："+display_time(r.get("analyzed_at", "")), parent=self)
            menu.add_command(label="查看评分详情", command=detail)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()


class ProgressBall(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#F5F1FF", width=114, height=126)
        self.pack_propagate(False)
        self.canvas = tk.Canvas(self, width=114, height=126, bg="#F5F1FF", highlightthickness=0, cursor="fleur")
        self.canvas.pack(fill="both", expand=True)
        self.score = None
        self.dragged = False
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        parent.bind("<Configure>", self.position, add="+")
        self.position(); self.render(None)

    def position(self, event=None):
        parent = self.master
        width, height = parent.winfo_width(), parent.winfo_height()
        if self.dragged:
            self.place(x=max(0, min(self.winfo_x(), width-114)), y=max(0, min(self.winfo_y(), height-126)))
        else:
            wanted_y = 92 if height >= 400 else 66 if height >= 330 else 32
            self.place(x=max(0,(width-114)//2), y=min(wanted_y, max(0, height-126)))
        self.lift()

    def start_drag(self, event):
        self.drag_origin = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())

    def drag(self, event):
        self.dragged = True
        x, y, left, top = self.drag_origin
        self.place(x=max(0, min(left+event.x_root-x, self.master.winfo_width()-114)),
                   y=max(0, min(top+event.y_root-y, self.master.winfo_height()-126)))

    def render(self, score):
        self.score = score
        c = self.canvas; c.delete("all")
        for size, color in [(2, "#EAE0FD"), (7, "#E0D3FA"), (13, "#FFFFFF")]:
            c.create_oval(size, size, 114-size, 114-size, fill=color, outline="")
        c.create_arc(10,10,104,104,start=90,extent=-359.9,style="arc",outline="#D5C8F0",width=5)
        if score is not None and score > 0:
            c.create_arc(10,10,104,104,start=90,extent=-score*3.599,style="arc",outline=PURPLE,width=5)
        c.create_text(57,35,text="攻略进度",font=ui_font(self,9),fill="#6D548F")
        c.create_text(57,62,text="--" if score is None else str(score)+"%",font=ui_font(self,21,True),fill=PURPLE)
        c.create_text(57,87,text="等待证据" if score is None else "文字互动信号",font=ui_font(self,8),fill="#715F8E")
        c.create_text(57,120,text="按住拖动",font=ui_font(self,8),fill="#73648C")
        theme_canvas(c)


class CharacterPanel(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#F5F1FF", width=194)
        self.pack_propagate(False)
        self.portrait = tk.Canvas(self, bg="#F5F1FF", highlightthickness=0, cursor="hand2")
        self.portrait.pack(fill="both", expand=True)
        self.name = tk.StringVar(value="对话人物")
        self.phase = tk.StringVar(value="等待建立档案")
        self.caption = tk.StringVar(value="已分析 0 / 0 条")
        self.metrics = {}
        self.has_profile=False
        for key, (name, _, _) in DIMENSIONS.items():
            variable = tk.StringVar(value=name+"   --")
            self.metrics[key] = variable
        self.portrait.bind("<Configure>", lambda e:self.draw_portrait())
        self.portrait.bind("<Button-1>", self.detail)
        self.draw_portrait()

    def draw_portrait(self):
        c = self.portrait;c.delete('all')
        width,height=c.winfo_width(),c.winfo_height();x=width/2
        c.create_oval(x-23,14,x+23,60,fill='#E8DDFC',outline='')
        c.create_oval(x-17,18,x+17,53,fill='#B29BE4',outline='')
        c.create_text(x,36,text=self.name.get()[:1] if self.has_profile else '?',fill='white',font=ui_font(self,14,True))
        c.create_text(x,76,text=self.name.get()[:11] if self.has_profile else '等待选择联系人',fill=INK,font=ui_font(self,10,True))
        ball_y=92 if height>=400 else 66 if height>=330 else 32
        base=ball_y+148
        if self.has_profile:
            c.create_text(x,base,text=self.phase.get(),fill=PURPLE,font=ui_font(self,9,True))
            c.create_text(x,base+22,text=self.caption.get(),fill='#586880',font=ui_font(self,8))
            row_height=22 if height>=400 else 18
            for i,variable in enumerate(self.metrics.values()):
                y=base+54+i*row_height
                if y<height-12:
                    c.create_text(12,y,text=variable.get(),anchor='w',fill='#586880',font=ui_font(self,9))
        else:
            c.create_text(x,base+14,text='选择联系人后\n这里展示互动变化',width=max(100,width-24),justify='center',fill='#586880',font=ui_font(self,9))
        theme_canvas(c)

    def detail(self, event=None):
        from tkinter import messagebox
        messagebox.showinfo("人物互动档案", self.name.get()+"\n"+self.phase.get()+"\n"+self.caption.get()+"\n\n"+
                            "\n".join(v.get() for v in self.metrics.values())+"\n\n攻略进度衡量已分析文字的互动信号。", parent=self)

    def update_progress(self, name, summary,has_profile=True):
        self.has_profile=has_profile
        self.name.set(name)
        score = summary["score"]
        self.phase.set("证据不足" if score is None else "第 1 章 · 初识" if score < 40 else "第 2 章 · 自然交流" if score < 65 else "第 3 章 · 积极互动" if score < 85 else "第 4 章 · 清晰积极")
        self.caption.set(f"已分析 {summary['analyzed']} / {summary['total']} 条")
        for key, variable in self.metrics.items():
            score = summary["dimensions"][key]
            variable.set(DIMENSIONS[key][0]+"   "+("--" if score is None else str(score)))
        self.draw_portrait()
