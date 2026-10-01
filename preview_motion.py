"""Record a synthetic page transition and inspect brightness / stable geometry."""
import json
import tempfile
import time
import tkinter as tk
from pathlib import Path
import numpy as np
from chat_assistant.app import AssistantApp
from chat_assistant.capture import enable_dpi_awareness,grab
from chat_assistant.core import Region
from chat_assistant.storage import SettingsStore

enable_dpi_awareness()
with tempfile.TemporaryDirectory() as folder:
    root=tk.Tk()
    app=AssistantApp(root,SettingsStore(Path(folder)),show_guide=False)
    root.geometry('1100x760+30+30');root.attributes('-topmost',True)
    root.update()
    frames=[];samples=[]
    region=Region(root.winfo_rootx(),root.winfo_rooty(),root.winfo_width(),root.winfo_height())
    started=time.perf_counter()
    def capture():
        shot=grab(region)
        frame=np.asarray(shot)[50:700,225:1050,:3]
        samples.append({'ms':round((time.perf_counter()-started)*1000,2),'dark_fraction':round(float(np.mean(np.all(frame<35,axis=2))),4),
                        'positions_stable':all((p.winfo_x(),p.winfo_y())==(0,0) for p in app.pages.values())})
        frames.append(shot)
    capture()
    app.show_page('设置')
    for delay in range(20,261,20):root.after(delay,capture)
    root.after(320,root.quit);root.mainloop()
    assert all(s['positions_stable'] and s['dark_fraction']<.1 for s in samples)
    # A fully invalidated reference detects old-page ghosting, which a simple
    # "no black pixels" check would miss. Only inspect the nonanimated body.
    import ctypes
    ctypes.windll.user32.RedrawWindow(ctypes.c_void_p(app.pages['设置'].winfo_id()),None,None,0x185)
    root.update();time.sleep(.04)
    reference=np.asarray(grab(region)).astype(int)
    panel=app.settings_panel;x=panel.winfo_rootx()-region.left;y=panel.winfo_rooty()-region.top
    body=np.s_[y:y+panel.winfo_height(),x:x+panel.winfo_width(),:3]
    for frame,sample in zip(frames[1:],samples[1:]):
        sample['stale_content_fraction']=round(float(np.mean(np.max(np.abs(np.asarray(frame).astype(int)[body]-reference[body]),axis=2)>12)),4)
        assert sample['stale_content_fraction']<.01,sample
    durations=[400]+[max(16,round(samples[i+1]['ms']-samples[i]['ms'])) for i in range(1,len(samples)-1)]+[800]
    frames[0].save('assets/v26-switch.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0)
    frames[4].save('assets/v26-switch-frame.png')
    Path('assets/transitions-visual.json').write_text(json.dumps(samples,indent=2),encoding='utf-8')
    print(json.dumps({'frames':len(frames),'coordinates_stable':True,'black_frames_detected':0,'largest_dark_fraction':max(s['dark_fraction'] for s in samples),'largest_stale_content_fraction':max(s.get('stale_content_fraction',0) for s in samples)}))
    app.close()
