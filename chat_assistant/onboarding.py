"""A local, skippable tour of real controls; never saves settings drafts or calls APIs."""
import json
import os
from pathlib import Path
import tkinter as tk

from .ui_fonts import ui_font
from .ui_themes import theme_color


class GuideState:
    def __init__(self, directory):
        self.path = Path(directory)/'ui_state.json'

    def read(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            return data if isinstance(data,dict) else {}
        except (OSError,ValueError):
            return {}

    @property
    def done(self):
        return self.read().get('onboarding') in ('completed','skipped')

    def finish(self, status):
        if status not in ('completed','skipped'):
            raise ValueError('Invalid tour state')
        data = self.read()
        data.update(onboarding=status,onboarding_version=1)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w',encoding='utf-8') as stream:
            json.dump(data,stream,ensure_ascii=False,indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)


class BeginnerGuide:
    def __init__(self, app):
        from .app import button, label
        self.app, self.root = app, app.root
        self.index = 0
        self.closed = False
        self.timer = None
        self.anchor = None
        self.pulse = False
        self.steps = [
            ('你好，欢迎来到聊有据', '导入记录', None,
             '跟着亮起来的位置，一步步认识软件。\n\n你可以随时跳过，之后在“使用说明”里再看。\n这段引导只介绍按钮，不会发起分析或扣费。'),
            ('① 先认识设置', '设置', lambda:app.save_button,
             '选择分析模型，在“接口设置”里填自己的 API Key。\n\nJev 用来评分；DeepSeek 可以解释消息、给回复建议。\n字体、主题和偏好改好后，点亮起的“保存设置”。'),
            ('② 把聊天记录放进来', '导入记录', lambda:app.import_center.import_button,
             '点“导入记录”，选聊天记录文件。\n\n还没有文件？旁边的 QQ / 微信按钮可以打开导出工具。\n导入预览里确认“哪位是我”，再保存档案。'),
            ('③ 选联系人，选时间', '导入记录', lambda:app.import_center.history.range_row,
             '先在左侧选联系人，再点击日期，打开日历选择起止日期。\n\n也可直接选“今日”“近7天”或“全部时间”。\n点“筛选”查看消息；“重置”恢复全部时间。'),
            ('④ 点开始评分，进度会保存', '导入记录', lambda:app.import_center.history.start_button,
             '点“开始评分”，每十条会保存一次，已分析的消息会显示评级。\n\n无法判断的消息会提醒所在页，接着分析下一组。\n中途退出也没关系，下次选联系人可以继续。'),
            ('⑤ 想知道理由，再点解释', '导入记录', lambda:app.import_center.history.chat,
             '右键一条消息，可以让 DeepSeek 解释。\n\n也可以点击几条气泡多选，再点“解释所选”。\n旁边的人物卡和进度球会随评分更新。'),
            ('⑥ 实时分析，等你需要再开启', '实时分析', lambda:app.live_button,
             '聊天正在进行时，用“框选聊天区”选消息气泡，再开始实时分析。\n\n建议出现后，你可以修改、复制，再自己发送。\n准备好了！点完成，回到导入记录开始使用。'),
        ]
        self.edges = [tk.Frame(self.root,bg=theme_color(self.root,'#6658D9')) for _ in range(4)]
        self.card = tk.Frame(self.root,bg='#FFFFFF',highlightthickness=2,highlightbackground='#6658D9',padx=22,pady=18)
        top = tk.Frame(self.card,bg='#FFFFFF');top.pack(fill='x')
        self.counter = tk.StringVar()
        tk.Label(top,textvariable=self.counter,bg='#FFFFFF',fg='#6658D9',font=ui_font(top,9,True)).pack(side='left')
        button(top,'跳过',self.skip,padx=9,pady=4).pack(side='right')
        self.title = tk.StringVar()
        tk.Label(self.card,textvariable=self.title,bg='#FFFFFF',fg='#24304A',font=ui_font(self.card,15,True),anchor='w',wraplength=352).pack(fill='x',pady=(12,10))
        self.content = tk.StringVar()
        tk.Label(self.card,textvariable=self.content,bg='#FFFFFF',fg='#586880',font=ui_font(self.card,10),justify='left',anchor='w',wraplength=352).pack(fill='x')
        self.dots = tk.Canvas(self.card,bg='#FFFFFF',height=15,highlightthickness=0)
        self.dots.pack(fill='x',pady=(12,8))
        footer=tk.Frame(self.card,bg='#FFFFFF');footer.pack(fill='x')
        self.back_button = button(footer,'上一步',self.back,padx=11,pady=7)
        self.back_button.pack(side='left')
        self.next_button = button(footer,'下一步  →',self.next,True,padx=16,pady=7)
        self.next_button.pack(side='right')
        self.binding = self.root.bind('<Configure>',self.layout_changed,add='+')
        self.show()
        self.tick()

    def show(self):
        title,page,anchor,content = self.steps[self.index]
        self.app.show_page(page,animate=False)
        if page == '设置':
            self.app.settings_panel.canvas.yview_moveto(1)
        if page == '导入记录':
            self.app.import_center.notebook.select(0)
        self.anchor = anchor() if anchor else None
        self.counter.set(f'新手任务  {self.index+1} / {len(self.steps)}')
        self.title.set(title)
        self.content.set(content)
        self.back_button.configure(state='disabled' if self.index==0 else 'normal')
        self.next_button.configure(text='完成  ✓' if self.index==len(self.steps)-1 else '下一步  →')
        self.dots.delete('all')
        for i in range(len(self.steps)):
            self.dots.create_oval(i*18+2,3,i*18+10,11,fill=theme_color(self.root,'#6658D9' if i<=self.index else '#DFE5F0'),outline='')
        self.app.fonts.apply(self.card)
        self.app.themes.apply(self.card)
        self.root.update_idletasks()
        self.position()

    def layout_changed(self,event):
        if event.widget == self.root and not self.closed:
            self.position()

    def position(self):
        if self.closed:
            return
        width,height = self.root.winfo_width(),self.root.winfo_height()
        cw = min(404, width-32)
        ch = self.card.winfo_reqheight()
        for edge in self.edges:
            edge.place_forget()
        x,y = (width-cw)//2,(height-ch)//2
        if self.anchor is not None and self.anchor.winfo_ismapped():
            ax = self.anchor.winfo_rootx()-self.root.winfo_rootx()
            ay = self.anchor.winfo_rooty()-self.root.winfo_rooty()
            aw,ah = self.anchor.winfo_width(),self.anchor.winfo_height()
            # Clip to the app window; a scrolled control may be partially visible.
            left,top,right,bottom = max(3,ax-4),max(3,ay-4),min(width-3,ax+aw+4),min(height-3,ay+ah+4)
            if right>left and bottom>top:
                self.edges[0].place(x=left,y=top,width=right-left,height=3)
                self.edges[1].place(x=left,y=bottom-3,width=right-left,height=3)
                self.edges[2].place(x=left,y=top,width=3,height=bottom-top)
                self.edges[3].place(x=right-3,y=top,width=3,height=bottom-top)
                if right+cw+16 <= width:
                    x,y = right+12,top
                elif top >= ch+24:
                    x,y = right-cw,top-ch-14
                else:
                    x,y = right-cw,bottom+14
        x=max(16,min(x,width-cw-16));y=max(16,min(y,height-ch-16))
        self.card.place(x=x,y=y,width=cw)
        for edge in self.edges:
            edge.lift()
        self.card.lift()

    def tick(self):
        if self.closed:
            return
        self.pulse=not self.pulse
        color=theme_color(self.root,'#6658D9' if self.pulse else '#B29BE4')
        for edge in self.edges:
            edge.configure(bg=color)
        self.card.configure(highlightbackground=theme_color(self.root,'#6658D9'))
        self.position()
        self.timer=self.root.after(420,self.tick)

    def next(self):
        if self.index == len(self.steps)-1:
            self.close('completed')
        else:
            self.index+=1
            self.show()

    def back(self):
        if self.index:
            self.index-=1
            self.show()

    def skip(self):
        self.close('skipped')

    def close(self, status=None):
        if self.closed:
            return
        if status:
            try:
                GuideState(self.app.store.directory).finish(status)
            except OSError:
                self.app.show_error('引导状态没有保存，请检查存档目录是否可写，再点击完成或跳过。')
                return
        self.closed=True
        if self.timer:
            self.root.after_cancel(self.timer)
        self.root.unbind('<Configure>',self.binding)
        for widget in [self.card,*self.edges]:
            widget.destroy()
        self.app.guide=None
        if status:
            self.app.show_page('导入记录',animate=False)
            self.app.set_status('引导已完成，可以从“导入记录”开始。使用说明中可重新查看引导。' if status=='completed' else '引导已跳过；需要时在“使用说明”重新查看。')
