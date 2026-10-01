"""Keep page geometry stable; soften headings and navigation without window opacity."""
import time
import os
import ctypes
import tkinter as tk
from tkinter import font as tkfont
from .ui_widgets import blend_color


def repaint_page(widget):
    """Invalidate the raised Windows surface, including cached child windows.

    Tk can retain pixels from the old sibling under newly exposed canvas
    children during its ordinary mainloop. Request their native paint once;
    do not erase the background first or pump a nested Tk event loop.
    """
    if os.name!='nt' or not widget.winfo_ismapped():return
    redraw=ctypes.WinDLL('user32',use_last_error=True).RedrawWindow
    redraw.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint]
    redraw.restype=ctypes.c_int
    redraw(widget.winfo_id(),None,None,0x001|0x080|0x100)  # INVALIDATE | ALLCHILDREN | UPDATENOW


class PageTransition:
    def __init__(self,container,pages,nav_buttons=None,duration=.18):
        self.container,self.pages=container,pages
        self.root=container.winfo_toplevel()
        self.nav_buttons=nav_buttons or {}
        self.duration=duration
        self.current=None
        self.timer=None
        self.closed=False
        self.title_fades=[]
        self.nav_fades=[]
        self.page_names={page:name for name,page in pages.items()}
        self.headings={}
        for page in pages.values():
            page.place(x=0,y=0,relwidth=1,relheight=1)
            self.headings[page]=[widget for widget in self.descendants(page) if isinstance(widget,tk.Label) and tkfont.Font(root=self.root,font=widget.cget('font')).actual('size')>=18]
            self.focus_tree(page,False)
        self.binding=container.bind('<Configure>',self.resized,add='+')
        self.map_binding=self.root.bind('<Map>',self.mapped,add='+')
        self.focus_binding=self.root.bind('<FocusIn>',self.focused,add='+')

    def descendants(self,widget):
        yield widget
        for child in widget.winfo_children():yield from self.descendants(child)

    def page_for(self,widget):
        while widget is not None:
            if widget in self.page_names:return self.page_names[widget]
            widget=getattr(widget,'master',None)

    def focus_widget(self,widget,allowed):
        if 'takefocus' not in widget.keys():return
        if not hasattr(widget,'_page_takefocus'):widget._page_takefocus=widget.cget('takefocus')
        value=widget._page_takefocus if allowed else '0'
        # Focus eligibility does not change appearance. Bypass custom configure
        # hooks that repaint a canvas button for every unrelated option change.
        if str(widget.cget('takefocus'))!=str(value):tk.Misc.configure(widget,takefocus=value)

    def focus_tree(self,page,allowed):
        for widget in self.descendants(page):self.focus_widget(widget,allowed)

    def mapped(self,event):
        if self.closed or not isinstance(event.widget,tk.Misc):return
        name=self.page_for(event.widget)
        if name is not None:self.focus_widget(event.widget,name==self.current)

    def focus_navigation(self):
        self.nav_buttons.get(self.current,self.container).focus_set()

    def focused(self,event):
        if self.closed or not isinstance(event.widget,tk.Misc):return
        name=self.page_for(event.widget)
        if name is not None and name!=self.current:self.focus_navigation()

    @property
    def running(self):
        return self.timer is not None

    def show(self,name,animate=True):
        page=self.pages[name]
        if self.closed:return
        if name==self.current:
            if not animate:self.finish()
            return
        previous=self.current
        self.finish()
        try:focus=self.root.focus_get()
        except (KeyError,tk.TclError):focus=None
        if previous:self.focus_tree(self.pages[previous],False)
        self.current=name
        self.focus_tree(page,True)
        page.lift()
        repaint_page(page)
        if focus is not None and self.page_for(focus) not in (None,name):self.focus_navigation()
        for title,nav in self.nav_buttons.items():nav.selected=title==name
        if not animate or previous is None or not self.container.winfo_ismapped():
            for nav in self.nav_buttons.values():nav.paint()
            return
        self.title_fades=[(widget,widget.cget('bg'),widget.cget('fg')) for widget in self.headings[page]]
        self.nav_fades=[(nav,1 if title==previous else 0,1 if title==name else 0) for title,nav in self.nav_buttons.items() if title in (previous,name)]
        self.started=time.perf_counter()
        self.paint(0)
        self.timer=self.container.after(16,self.step)

    def paint(self,progress):
        for widget,background,foreground in self.title_fades:
            widget.configure(fg=blend_color(widget,background,foreground,.4+.6*progress))
        for nav,start,end in self.nav_fades:
            nav.selection_progress=start+(end-start)*progress
            nav.paint()

    def step(self):
        self.timer=None
        if self.closed:return
        progress=min(1,(time.perf_counter()-self.started)/self.duration)
        if progress>=1:
            self.finish()
            return
        self.paint(progress*progress*(3-2*progress))
        self.timer=self.container.after(16,self.step)

    def finish(self):
        if self.timer:
            self.container.after_cancel(self.timer)
            self.timer=None
        for widget,_,foreground in self.title_fades:widget.configure(fg=foreground)
        for nav,_,_ in self.nav_fades:
            nav.selection_progress=None;nav.paint()
        self.title_fades=[];self.nav_fades=[]

    def resized(self,event):
        if event.widget==self.container and not self.closed:self.finish()

    def close(self):
        if self.closed:return
        self.finish()
        self.closed=True
        self.container.unbind('<Configure>',self.binding)
        self.root.unbind('<Map>',self.map_binding)
        self.root.unbind('<FocusIn>',self.focus_binding)
