"""Time only synthetic app page switches; never read actual account state."""
import json
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path
from chat_assistant.app import AssistantApp
from chat_assistant.capture import enable_dpi_awareness
from chat_assistant.storage import SettingsStore

enable_dpi_awareness()
with tempfile.TemporaryDirectory() as folder:
    root=tk.Tk()
    app=AssistantApp(root,SettingsStore(Path(folder)),show_guide=False)
    root.geometry('1100x760')
    root.update()
    records=[]
    font_apply,theme_apply=app.fonts.apply,app.themes.apply
    counts={'font_walks':0,'theme_walks':0,'maps':0}
    def counted_font(widget):
        counts['font_walks']+=1;font_apply(widget)
    def counted_theme(widget):
        counts['theme_walks']+=1;theme_apply(widget)
    app.fonts.apply=counted_font;app.themes.apply=counted_theme
    root.bind_all('<Map>',lambda e:counts.update(maps=counts['maps']+1),add='+')
    for name in ['设置','实时分析','导入记录','使用说明','设置','导入记录']:
        counts.update(font_walks=0,theme_walks=0,maps=0)
        t=time.perf_counter();app.show_page(name)
        dispatch=(time.perf_counter()-t)*1000
        root.update()
        records.append({'page':name,'dispatch_ms':round(dispatch,2),'settled_ms':round((time.perf_counter()-t)*1000,2),**counts})
        if hasattr(app,'page_transition'):
            while app.page_transition.running:
                root.update();time.sleep(.005)
            records[-1]['animation_ms']=round((time.perf_counter()-t)*1000,2)
    app.close()
    Path(sys.argv[1] if len(sys.argv)>1 else 'assets/transitions-after.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(records,ensure_ascii=False))
