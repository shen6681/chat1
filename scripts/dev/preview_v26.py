"""Capture the application's own windows with temporary synthetic data only."""
import tempfile
import sys
import time
import tkinter as tk
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from chat_assistant.app import AssistantApp
from chat_assistant.capture import enable_dpi_awareness,grab
from chat_assistant.core import Region,Message
from chat_assistant.storage import SettingsStore
from tests.test_history import rating

enable_dpi_awareness()
root=tk.Tk()
with tempfile.TemporaryDirectory() as folder:
    app=AssistantApp(root,SettingsStore(Path(folder)),show_guide=False)
    root.geometry('1360x920+20+20');root.attributes('-topmost',True)
    def capture(name,widget=root):
        end=time.monotonic()+.3
        while time.monotonic()<end:root.update();time.sleep(.01)
        grab(Region(widget.winfo_rootx(),widget.winfo_rooty(),widget.winfo_width(),widget.winfo_height())).save(Path(__file__).resolve().parents[2]/'docs'/'images'/name)
    app.set_status('界面演示 · 合成消息 · 不调用 API')
    capture('v26-empty.png')
    p=app.archives.create('林夏 · 演示','微信','demo','self')
    texts=['上次你推荐的电影，我看完了。','怎么样？你喜欢那个结尾吗？','挺喜欢的！我还在想最后那段对话。','我也是。周六有空的话，要不要一起看新上映那部？','好啊，我们一起选个时间吧。','下午三点怎么样？周末放松一下。']
    app.archives.import_messages(p.id,[Message('我' if i%2==0 else '对方',t,timestamp=f'2026-10-01T20:0{i}:00+08:00',message_id=str(i)) for i,t in enumerate(texts)])
    for e in app.archives.entries(p.id):
        r=rating(e.message.speaker,score=75);r['source']='TypeSafe Jev / 固定演示数据'
        app.archives.save_rating(p.id,e.id,r,'demo','demo')
    for name in ('周可 · 演示','陈默 · 演示'):
        app.archives.create(name,'微信',name,'self')
    app.import_center.refresh(p.id)
    history=app.import_center.history
    history.start_var.set('2026-10-01');history.end_var.set('2026-10-01');history.apply_range()
    capture('v26-history.png')
    root.geometry('1100x760+20+20');capture('v26-history-small.png')
    picker=history.start_picker.open();picker.set_month(2026,10);picker.choose_day(1)
    capture('v26-picker.png',picker.window);capture('v26-picker-in-app.png')
    picker.close()
    history.range_tooltip.show();capture('v26-tooltip.png');history.range_tooltip.hide()
    app.show_page('设置');capture('v26-settings-small.png')
    app.show_page('导入记录')
    app.theme_var.set('樱花粉');app.surface_var.set('雾蓝');app.preview_theme();capture('v26-pink-mist.png')
    app.start_guide();app.guide.next();app.guide.next();app.guide.next();capture('v26-guide.png');app.guide.skip()
    app.font_var.set('站酷快乐体 · 俏皮圆润');app.preview_font();capture('v26-kuaile-small.png')
    app.close()
