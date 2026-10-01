"""Small Tk presentation widgets that retain the existing selection and theme APIs."""
import tkinter as tk
from .ui_fonts import ui_font
from .ui_themes import theme_color, theme_canvas, theme_book


def blend_color(widget,start,end,amount):
    amount=max(0,min(1,amount))
    if amount==0:return start
    if amount==1:return end
    a,b=widget.winfo_rgb(start),widget.winfo_rgb(end)
    return '#'+''.join(f'{round((x+(y-x)*amount)/257):02x}' for x,y in zip(a,b))


def rounded_rect(canvas,x1,y1,x2,y2,fill,outline='',radius=6,tags=()):
    r=min(radius,max(0,(x2-x1)/2),max(0,(y2-y1)/2))
    points=[x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1]
    return canvas.create_polygon(points,smooth=True,splinesteps=16,fill=fill,outline=outline or fill,width=1,tags=tags)


class Card(tk.Frame):
    def __init__(self,parent,padding=14,**options):
        super().__init__(parent,bg=parent.cget('bg'),**options)
        self.radius=6
        self.padding=padding
        self.canvas=tk.Canvas(self,bg=parent.cget('bg'),highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.body=tk.Frame(self.canvas,bg='#FFFFFF')
        self.item=self.canvas.create_window(padding,padding,window=self.body,anchor='nw')
        self.canvas.bind('<Configure>',self.draw)

    def draw(self,event=None):
        width,height=self.canvas.winfo_width(),self.canvas.winfo_height()
        self.canvas.delete('card-border')
        rounded_rect(self.canvas,1,1,width-1,height-1,'#FFFFFF','#DFE5F0',6,('card-border',))
        self.canvas.tag_lower('card-border')
        self.canvas.itemconfigure(self.item,width=max(1,width-self.padding*2),height=max(1,height-self.padding*2))
        theme_canvas(self.canvas)


class Tooltip:
    def __init__(self,widget,text,delay=500):
        self.widget,self.text,self.delay=widget,text,delay
        self.window=None
        self.timer=None
        widget.bind('<Enter>',lambda e:self.schedule(),add='+')
        widget.bind('<Leave>',lambda e:self.hide(),add='+')
        widget.bind('<ButtonPress>',lambda e:self.hide(),add='+')
        widget.bind('<FocusIn>',lambda e:self.schedule(),add='+')
        widget.bind('<FocusOut>',lambda e:self.hide(),add='+')
        widget.bind('<Destroy>',self.destroyed,add='+')

    def schedule(self):
        self.hide()
        self.timer=self.widget.after(self.delay,self.show)

    def show(self):
        self.timer=None
        if self.window or not self.widget.winfo_exists() or not self.widget.winfo_ismapped():
            return
        window=self.window=tk.Toplevel(self.widget)
        # Tk destroys child toplevels before sending their parent's Destroy.
        # Detach here so parent teardown cannot destroy the same Tcl commands twice.
        window.bind('<Destroy>',lambda e:self.window_destroyed(e,window),add='+')
        window.withdraw();window.overrideredirect(True)
        window.transient(self.widget.winfo_toplevel())
        window.configure(bg=theme_color(self.widget,'#DFE5F0'))
        text=self.text() if callable(self.text) else self.text
        tk.Label(window,text=text,bg=theme_color(self.widget,'#FFFFFF'),fg=theme_color(self.widget,'#24304A'),
                 wraplength=330,justify='left',font=ui_font(self.widget,9),padx=12,pady=10).pack(padx=1,pady=1)
        window.update_idletasks()
        width,height=window.winfo_reqwidth(),window.winfo_reqheight()
        # Position in the owning app, so a long tip stays on screen and in visual QA captures.
        owner=self.widget.winfo_toplevel()
        left,top=owner.winfo_rootx(),owner.winfo_rooty()
        x=max(left+6,min(self.widget.winfo_rootx(),left+owner.winfo_width()-width-6))
        y=self.widget.winfo_rooty()+self.widget.winfo_height()+6
        if y+height>top+owner.winfo_height()-6:
            y=max(top+6,self.widget.winfo_rooty()-height-6)
        window.geometry(f'+{x}+{y}');window.deiconify()
        window.lift()

    def hide(self):
        if self.timer:
            try:self.widget.after_cancel(self.timer)
            except tk.TclError:pass
            self.timer=None
        if self.window:
            window,self.window=self.window,None
            try:window.destroy()
            except tk.TclError:pass

    def window_destroyed(self,event,window):
        if event.widget==window and self.window==window:self.window=None

    def destroyed(self,event):
        if event.widget==self.widget:self.hide()


class ContactList(tk.Listbox):
    def __init__(self,parent,**options):
        super().__init__(parent,**options)
        self.hover_index=-1
        self.bind('<Motion>',self.hover_at,add='+')
        self.bind('<Leave>',lambda e:self.clear_hover(),add='+')

    def hover_at(self,event):
        index=self.nearest(event.y) if self.size() else -1
        bounds=self.bbox(index) if index>=0 else None
        if not bounds or not bounds[1]<=event.y<bounds[1]+bounds[3]:index=-1
        if index!=self.hover_index:
            self.clear_hover();self.hover_index=index
            if index>=0:self.itemconfigure(index,background=theme_color(self,'#EEF1FA'))

    def clear_hover(self):
        if 0<=self.hover_index<self.size():self.itemconfigure(self.hover_index,background=self.cget('bg'))
        self.hover_index=-1

    def refresh_theme(self):
        for index in range(self.size()):
            self.itemconfigure(index,background=theme_color(self,'#EEF1FA') if index==self.hover_index else self.cget('bg'),foreground=self.cget('fg'))
