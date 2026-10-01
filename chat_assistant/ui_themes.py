"""Window-scoped palettes for Tk, ttk, new dialogs and redrawn canvas content."""
import tkinter as tk
from tkinter import ttk

from .ui_fonts import ui_font

THEMES = {'清透蓝':'blue','雾紫':'lavender', '樱花粉':'sakura', '薄荷绿':'mint', '晴空蓝':'sky', '奶杏':'peach'}
SURFACE_SCHEMES = {'跟随主题':'theme','浅灰':'gray','冷白':'white','雾蓝':'mist','暖米':'cream'}
SURFACES = {
    'gray':{'bg':'#F3F4F6','surface':'#ECEFF3','character':'#F5F6F8','chat':'#F7F8FA'},
    'white':{'bg':'#F9FAFC','surface':'#F0F2F5','character':'#FAFBFD','chat':'#FBFCFE'},
    'mist':{'bg':'#EDF3FA','surface':'#E5EDF7','character':'#F0F5FC','chat':'#F4F7FC'},
    'cream':{'bg':'#F8F4EF','surface':'#F1EAE1','character':'#FAF6F0','chat':'#FBF8F4'},
}

# Baseline literals are the existing view's semantic colors. Images remain unchanged.
GROUPS = {
    'bg':('#F4F6FB',),
    'panel':('#FFFFFF','white'),
    'surface':('#EEF1FA','#F4F3F8'),
    'border':('#DFE5F0','#C3CDD7','#CAD3DC'),
    'text':('#24304A','#17211B'),
    'muted':('#586880','#536279','#667789','#88919F','#6D548F','#715F8E','#73648C','#6E5B8E'),
    'accent':('#6658D9','#7157DA'),
    'light':('#EBE8FC','#DED9F8','#EAE0FD','#E8DDFC'),
    'hover':('#574BC4',),
    'hover_light':('#E4E7F3',),
    'character':('#F5F1FF',),
    'avatar':('#CEC4F5','#E0D3FA','#D5C8F0'),
    'portrait':('#B29BE4',),
    'chat':('#EEF2F5','#EDEDED'),
    'bubble':('#95EC69',),
    'bubble_border':('#77BC55',),
}
BASE = {color:color for colors in GROUPS.values() for color in colors}


def palette(bg, surface, border, text, muted, accent, light, hover, character, avatar, portrait, chat, bubble, bubble_border):
    roles = dict(bg=bg,panel='#FFFFFF',surface=surface,border=border,text=text,muted=muted,accent=accent,
                 light=light,hover=hover,hover_light=light,character=character,avatar=avatar,portrait=portrait,
                 chat=chat,bubble=bubble,bubble_border=bubble_border)
    return {color:roles[role] for role, colors in GROUPS.items() for color in colors}


PALETTES = {
    'blue':palette('#F3F5F8','#EDF1F6','#D8DFE9','#263247','#68758A','#3b7edd','#E6EFFC','#326ECA','#F5F7FB','#CCDDF6','#82A8DA','#F7F9FC','#DCEBFC','#A4C3EC'),
    'lavender': BASE,
    'sakura':palette('#FFF5F8','#FCEAF1','#E7C9D5','#392A35','#795766','#AE3F6A','#FAE0EB','#923354','#FFF0F5','#F0C7D9','#BF6B90','#FBF0F4','#F6D5E3','#CD8CA9'),
    'mint':palette('#F1F8F5','#E6F2EC','#C5DED2','#233B32','#527465','#227453','#D6EDDF','#185D41','#EDF8F0','#B6DBCA','#65A58B','#EBF3EF','#C5E9D5','#6AAE87'),
    'sky':palette('#F3F8FF','#E7F0FA','#CBDDEE','#26374B','#58718A','#336CAE','#DCEBFA','#285B94','#EFF6FF','#BED7EF','#719DCF','#EDF3FA','#D0E5FA','#89B3DE'),
    'peach':palette('#FFF8F0','#FAEEE0','#E6D3BC','#3C3228','#7C6955','#97602D','#F8E5CC','#7D4D22','#FFF4E5','#EDD4AF','#BA9663','#F7F0E7','#F5DFBF','#CBA777'),
}


def theme_book(widget):
    while widget is not None:
        book = getattr(widget,'_chat_theme_book',None)
        if book:
            return book
        widget = getattr(widget,'master',None)


def theme_color(widget, color):
    book = theme_book(widget)
    return book.color(color) if book else color


def theme_canvas(canvas):
    book = theme_book(canvas)
    if book:
        book.apply_canvas(canvas)


class ThemeBook:
    OPTIONS = ('background','foreground','activebackground','activeforeground','selectbackground',
               'selectforeground','insertbackground','highlightbackground','highlightcolor','selectcolor',
               'disabledforeground','troughcolor')

    def __init__(self, root, name='blue', surface_scheme='theme'):
        self.root = root
        self.name = name
        self.previous = BASE
        self.surface_scheme = surface_scheme
        self.palette = self.make_palette()
        self.revision=0
        root._chat_theme_book = self
        root.bind_all('<Map>', self.on_map, add='+')

    def color(self, original):
        return self.palette.get(original, original)

    def make_palette(self):
        colors=dict(PALETTES[self.name])
        for role,color in SURFACES.get(self.surface_scheme,{}).items():
            for original in GROUPS[role]:colors[original]=color
        return colors

    def canonical(self, value):
        if value in BASE:
            return value
        for palette in (self.previous,self.palette):
            original=next((base for base,color in palette.items() if color==value),None)
            if original:
                return original
        return value

    def set(self, name, surface_scheme=None):
        self.revision+=1
        self.previous = self.palette
        self.name = name
        if surface_scheme is not None:self.surface_scheme=surface_scheme
        self.palette=self.make_palette()
        self.styles()
        self.apply(self.root)

    def apply(self, widget):
        self.apply_one(widget)
        for child in widget.winfo_children():
            self.apply(child)

    def apply_one(self, widget):
        try:
            originals = getattr(widget,'_theme_originals',{})
            keys = widget.keys()
            for option in self.OPTIONS:
                if option in keys:
                    current = str(widget.cget(option))
                    if option not in originals or current not in (self.color(originals[option]),self.previous.get(originals[option],originals[option])):
                        # Explicit view updates are allowed; never overwrite semantic warn colors.
                        originals[option] = self.canonical(current)
                    value = self.color(originals[option])
                    if current != value:
                        if isinstance(widget,tk.Canvas):
                            tk.Canvas.configure(widget,**{option:value})
                        else:
                            widget.configure(**{option:value})
            widget._theme_originals = originals
            if hasattr(widget,'refresh_theme'):
                widget.refresh_theme()
            if isinstance(widget,tk.Canvas):
                self.apply_canvas(widget)
            widget._theme_revision=(id(self),self.revision)
        except tk.TclError:
            pass

    def apply_canvas(self, canvas):
        old = getattr(canvas,'_theme_items',{})
        live = {}
        for item in canvas.find_all():
            live[item] = {}
            options = canvas.itemconfigure(item)
            for option in ('fill','outline'):
                if option not in options:
                    continue
                current = canvas.itemcget(item,option)
                base = old.get(item,{}).get(option)
                if base is None or current not in (self.color(base),self.previous.get(base,base)):
                    base = self.canonical(current)
                live[item][option] = base
                canvas.itemconfigure(item,**{option:self.color(base)})
        canvas._theme_items = live

    def on_map(self, event):
        if isinstance(event.widget,tk.Misc) and getattr(event.widget,'_theme_revision',None)!=(id(self),self.revision):
            self.apply_one(event.widget)

    def styles(self):
        c = self.color
        style = ttk.Style(self.root)
        if style.theme_use() != 'clam':
            style.theme_use('clam')
        style.configure('TNotebook',background=c('#FFFFFF'),borderwidth=0,lightcolor=c('#FFFFFF'),darkcolor=c('#FFFFFF'),bordercolor=c('#DFE5F0'))
        style.configure('TNotebook.Tab',background=c('#FFFFFF'),foreground=c('#586880'),padding=(15,8),font=ui_font(self.root,10),borderwidth=0)
        style.map('TNotebook.Tab',background=[('selected',c('#EBE8FC'))],foreground=[('selected',c('#6658D9'))])
        style.configure('TCombobox',fieldbackground=c('#F4F6FB'),background=c('#EEF1FA'),foreground=c('#24304A'),arrowcolor=c('#586880'),bordercolor=c('#DFE5F0'),font=ui_font(self.root,10))
        style.map('TCombobox',fieldbackground=[('readonly',c('#F4F6FB'))],foreground=[('readonly',c('#24304A'))],background=[('active',c('#E4E7F3'))])
        style.configure('TScrollbar',background=c('#EEF1FA'),troughcolor=c('#FFFFFF'),borderwidth=0,arrowcolor=c('#586880'))
        style.configure('Signal.Horizontal.TProgressbar',background=c('#6658D9'),troughcolor=c('#F4F6FB'),borderwidth=0,thickness=5)
        for option, value in (('background','#FFFFFF'),('foreground','#24304A'),('selectBackground','#EBE8FC'),('selectForeground','#6658D9')):
            self.root.option_add('*TCombobox*Listbox.'+option,c(value))
