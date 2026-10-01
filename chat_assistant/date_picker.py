"""Local date picking with an optional clock, preserving the archive's Beijing time bounds."""
import calendar
from datetime import date,datetime,timedelta
import tkinter as tk
from tkinter import ttk

from .history_analysis import LOCAL_TIME
from .ui_fonts import ui_font
from .ui_themes import theme_color,theme_book
from .ui_widgets import Tooltip


def beijing_today():
    return datetime.now(LOCAL_TIME).date()


class DateField(tk.Frame):
    def __init__(self,parent,variable,placeholder,validator=None,on_change=None):
        from .app import button
        super().__init__(parent,bg=parent.cget('bg'))
        self.variable,self.placeholder,self.validator,self.on_change=variable,placeholder,validator,on_change
        self.popup=None
        self.button=button(self,'',self.open,padx=10,pady=6,font=ui_font(self,9),bg='#F4F6FB')
        self.button.pack(fill='x')
        self.trace=variable.trace_add('write',lambda *_:self.refresh())
        self.bind('<Destroy>',self.destroyed,add='+')
        self.tip=Tooltip(self.button,lambda:(variable.get() or '不限时间')+'\n点击打开日历；需要时可精确到秒。')
        self.refresh()

    def refresh(self):
        value=self.variable.get()
        self.button.configure(text=(value[:10]+(' *' if len(value)>10 else '') if value else self.placeholder)+'  ▾')

    def open(self):
        if self.popup and self.popup.window.winfo_exists():
            self.popup.window.lift();return self.popup
        self.popup=DatePopup(self)
        return self.popup

    def destroyed(self,event):
        if event.widget==self:
            self.variable.trace_remove('write',self.trace)
            if self.popup:self.popup.close()


class DatePopup:
    def __init__(self,field):
        from .app import button,label
        self.field=field
        self.window=tk.Toplevel(field)
        self.window.withdraw();self.window.title('选择日期 · '+field.placeholder)
        self.window.transient(field.winfo_toplevel());self.window.resizable(False,False)
        self.window.configure(bg='#FFFFFF')
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.bind('<Escape>',lambda e:self.close())
        self.window.bind('<Return>',lambda e:self.confirm())
        self.previous_grab=self.window.grab_current()
        today=beijing_today()
        raw=field.variable.get().strip().replace('/','-')
        try:self.selected_date=date.fromisoformat(raw[:10]) if raw else today
        except ValueError:self.selected_date=today
        self.year,self.month=self.selected_date.year,self.selected_date.month
        self.time_enabled=tk.BooleanVar(self.window,value=len(raw)>10)
        clock=raw[11:].split(':') if len(raw)>10 else []
        self.hour=tk.StringVar(self.window,value=clock[0] if clock else '00')
        self.minute=tk.StringVar(self.window,value=clock[1] if len(clock)>1 else '00')
        self.second=tk.StringVar(self.window,value=clock[2] if len(clock)>2 else '整分钟' if len(clock)==2 else '00')
        frame=tk.Frame(self.window,bg='#FFFFFF',padx=16,pady=14);frame.pack(fill='both')
        label(frame,'选择日期',14,bold=True).pack(anchor='w')
        header=tk.Frame(frame,bg='#FFFFFF');header.pack(fill='x',pady=(12,8))
        button(header,'‹',lambda:self.move_month(-1),padx=8,pady=4).pack(side='left')
        self.year_var=tk.StringVar(self.window,value=str(self.year))
        years=sorted(set(range(1900,2101))|{self.year})
        self.year_combo=ttk.Combobox(header,textvariable=self.year_var,values=years,state='readonly',width=5)
        self.year_combo.pack(side='left',padx=(12,3));label(header,'年',9).pack(side='left')
        self.month_var=tk.StringVar(self.window,value=str(self.month))
        self.month_combo=ttk.Combobox(header,textvariable=self.month_var,values=range(1,13),state='readonly',width=3)
        self.month_combo.pack(side='left',padx=(8,3));label(header,'月',9).pack(side='left')
        self.year_combo.bind('<<ComboboxSelected>>',self.month_selected)
        self.month_combo.bind('<<ComboboxSelected>>',self.month_selected)
        button(header,'›',lambda:self.move_month(1),padx=8,pady=4).pack(side='right')
        self.days=tk.Frame(frame,bg='#FFFFFF');self.days.pack(fill='x')
        self.day_buttons={}
        row=tk.Frame(frame,bg='#FFFFFF');row.pack(fill='x',pady=(10,6))
        button(row,'回到今天',self.today,padx=10,pady=5).pack(side='left')
        self.chosen=tk.StringVar(self.window)
        tk.Label(row,textvariable=self.chosen,bg='#FFFFFF',fg='#6658D9',font=ui_font(row,9)).pack(side='right')
        row=tk.Frame(frame,bg='#FFFFFF');row.pack(fill='x',pady=5)
        tk.Checkbutton(row,text='精确到时间',variable=self.time_enabled,bg='#FFFFFF',fg='#586880',selectcolor='#F4F6FB',
                       activebackground='#FFFFFF',font=ui_font(row,9),command=self.update_clock,bd=0,highlightthickness=0).pack(side='left')
        self.clock_boxes=[]
        for variable,maximum in ((self.hour,24),(self.minute,60),(self.second,60)):
            seconds=variable is self.second
            box=ttk.Combobox(row,textvariable=variable,values=(['整分钟'] if seconds else [])+[f'{i:02d}' for i in range(maximum)],state='readonly',width=5 if seconds else 3)
            box.pack(side='left',padx=3);self.clock_boxes.append(box)
            if seconds:Tooltip(box,'选择整分钟会保留分钟精度；结束时间包括该分钟的全部秒。选择具体秒则精确到该秒。')
        self.error=tk.StringVar(self.window)
        tk.Label(frame,textvariable=self.error,bg='#FFFFFF',fg='#A56B14',wraplength=310,justify='left',font=ui_font(frame,9)).pack(fill='x',pady=(2,7))
        footer=tk.Frame(frame,bg='#FFFFFF');footer.pack(fill='x')
        button(footer,'取消',self.close,padx=11,pady=7).pack(side='left')
        button(footer,'确定',self.confirm,True,padx=16,pady=7).pack(side='right')
        self.render();self.update_clock()
        self.window.deiconify();self.window.update_idletasks()
        self.position()
        self.window.grab_set();self.window.focus_set()

    def position(self):
        # Geometry places the native frame; root coordinates refer to the client
        # area. Include the measured title bar so the footer stays inside the app.
        window=self.window;field=self.field
        window.update_idletasks()
        width,height=window.winfo_reqwidth(),window.winfo_reqheight()
        frame_x=window.winfo_rootx()-window.winfo_x()
        frame_y=window.winfo_rooty()-window.winfo_y()
        owner=field.winfo_toplevel();left,top=owner.winfo_rootx(),owner.winfo_rooty()
        x=max(left+12,min(field.winfo_rootx(),left+owner.winfo_width()-width-2*frame_x-12))
        y=max(top+12,min(field.winfo_rooty()+field.winfo_height()+6,top+owner.winfo_height()-height-frame_y-12))
        window.geometry(f'+{x}+{y}')

    def render(self):
        from .app import button
        for child in self.days.winfo_children():child.destroy()
        self.day_buttons={}
        for column,text in enumerate('一二三四五六日'):
            tk.Label(self.days,text=text,bg='#FFFFFF',fg='#586880',font=ui_font(self.days,9),pady=5).grid(row=0,column=column,sticky='ew')
            self.days.columnconfigure(column,weight=1)
        for row,week in enumerate(calendar.Calendar(firstweekday=0).monthdayscalendar(self.year,self.month),1):
            for column,day in enumerate(week):
                if day:
                    selected=date(self.year,self.month,day)==self.selected_date
                    cell=button(self.days,str(day),lambda d=day:self.choose_day(d),padx=8,pady=6,font=ui_font(self.days,9))
                    cell.selected=selected;cell.paint()
                    cell.grid(row=row,column=column,padx=2,pady=2,sticky='ew');self.day_buttons[day]=cell
                else:tk.Frame(self.days,bg='#FFFFFF',height=30).grid(row=row,column=column)
        self.chosen.set(self.selected_date.isoformat())
        book=theme_book(self.window)
        if book:book.apply(self.window)
        if self.window.winfo_ismapped():self.position()

    def set_month(self,year,month):
        self.year,self.month=int(year),int(month)
        self.year_var.set(str(self.year));self.month_var.set(str(self.month))
        self.render()

    def month_selected(self,event=None):
        self.set_month(self.year_var.get(),self.month_var.get())

    def move_month(self,step):
        total=(self.year-1)*12+self.month-1+step
        if 0<=total<9999*12:self.set_month(total//12+1,total%12+1)

    def choose_day(self,day):
        self.selected_date=date(self.year,self.month,day);self.error.set('');self.render()

    def today(self):
        self.selected_date=beijing_today();self.set_month(self.selected_date.year,self.selected_date.month)

    def update_clock(self):
        for box in self.clock_boxes:box.configure(state='readonly' if self.time_enabled.get() else 'disabled')

    def confirm(self):
        value=self.selected_date.isoformat()
        try:
            if self.time_enabled.get():
                minute_precision=self.second.get()=='整分钟'
                h,m,s=int(self.hour.get()),int(self.minute.get()),0 if minute_precision else int(self.second.get())
                datetime(self.selected_date.year,self.selected_date.month,self.selected_date.day,h,m,s)
                value+=f' {h:02d}:{m:02d}'+('' if minute_precision else f':{s:02d}')
            if self.field.validator:self.field.validator(value)
        except ValueError as error:
            self.error.set(str(error));return
        self.field.variable.set(value)
        if self.field.on_change:self.field.on_change()
        self.close()

    def close(self):
        if self.window.winfo_exists():
            self.window.grab_release();self.window.destroy()
            if self.previous_grab and self.previous_grab.winfo_exists():self.previous_grab.grab_set()
