"""Manual UI preview using synthetic data and no model/network calls.

Run from the repository root: python -m tests.preview_affinity
"""
import tempfile
import threading
from pathlib import Path

from chat_assistant.core import Message
from chat_assistant.web_backend import LocalService
from chat_assistant.web_server import make_server


def main():
    with tempfile.TemporaryDirectory(prefix='chat1-affinity-preview-') as directory:
        service = LocalService(Path(directory))
        service.preferences['guideDone'] = True
        profile = service.store.create('小林（合成演示）', '微信', 'preview', 'self').id
        texts = ['这周要不要一起看展？不方便也没关系。', '周六可以呀，我来找一下展览信息😭', '好，我也看看路线。', '今天有点累，明天再聊可以吗？']
        service.store.import_messages(profile, [Message('我' if i % 2 == 0 else '对方', texts[i % 4], message_id=str(i)) for i in range(100)])
        entries = service.store.entries(profile)
        evidence = [{'entryId': entries[i].id, 'quote': entries[i].message.text, 'signal': signal} for i, signal in [(0, '主动邀约，同时给对方拒绝空间，是我方亲近意愿的线索。'), (1, '明确接受周六邀约并主动查信息；哭泣表情在此不能直接当作悲伤或好感下降。'), (3, '表达疲惫并提出明天再聊，是休息边界，不等于拒绝关系。')]]
        result = {'rawDelta': 4, 'confidence': .8, 'summary': '合成演示：双方在具体安排上有来有回，愿意继续接触。休息需求不应被误判为疏远。', 'evidence': evidence,
                  'personality': [{'text': '这段聊天中，对方倾向直接表达安排与休息需求；仅凭本段不能判断稳定人格。', 'evidenceIds': [entries[3].id]}],
                  'pursuitAdvice': [{'text': '明天再确认一个展览选项：“我找到一个周六的展，你觉得怎么样？”若对方取消且不愿另约，先暂停推进。', 'evidenceIds': [entries[1].id, entries[3].id]}],
                  'uncertainties': ['仅为合成界面演示，未调用模型。']}
        service.affinity.commit(profile, entries, result, '合成演示')
        service.self_affinity.commit(profile, entries, {**result, 'rawDelta': 2}, '合成演示')
        server = make_server(Path(__file__).resolve().parents[1] / 'web' / 'dist', service)
        print(f'http://127.0.0.1:{server.server_port}', flush=True)
        threading.Timer(600, server.shutdown).start()
        try: server.serve_forever()
        finally:
            server.server_close()
            service.close()


if __name__ == '__main__': main()
