"""Independent relationship signal, with atomic 100-message checkpoints."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone


def validate_result(raw, entries, perspective='other'):
    if not isinstance(raw, dict): raise ValueError('好感度分析没有返回 JSON 对象。')
    def number(name, low, high):
        v = raw.get(name)
        if type(v) not in (float, int) or not math.isfinite(v) or not low <= v <= high:
            raise ValueError('好感度分析数值无效，未计入进度。')
        return v
    delta, confidence = number('rawDelta', -10, 10), number('confidence', 0, 1)
    summary = raw.get('summary')
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 3000:
        raise ValueError('好感度分析缺少详细说明。')
    by_id = {e.id: e for e in entries}; evidence = raw.get('evidence')
    if not isinstance(evidence, list) or len(evidence) > 12: raise ValueError('好感度证据格式无效。')
    checked = []
    for row in evidence:
        if not isinstance(row, dict): raise ValueError('好感度证据格式无效。')
        entry = by_id.get(row.get('entryId'))
        quote, signal = row.get('quote'), row.get('signal')
        if type(row.get('entryId')) is not int or not entry or not isinstance(quote, str) or not quote.strip() or len(quote) > 1000 or quote not in entry.message.text:
            raise ValueError('模型引用不属于本批原文，未计入好感度。')
        if not isinstance(signal, str) or len(signal) > 1000: raise ValueError('好感度证据说明无效。')
        checked.append({'entryId':entry.id, 'quote':quote, 'signal':signal, 'speaker':entry.message.speaker})
    uncertainties = raw.get('uncertainties', [])
    if not isinstance(uncertainties, list) or len(uncertainties)>12 or any(not isinstance(x,str) or len(x)>1000 for x in uncertainties):
        raise ValueError('好感度疑点格式无效。')
    insights = {}
    for name in ('personality', 'pursuitAdvice'):
        rows = raw.get(name, [])
        if not isinstance(rows, list) or len(rows) > 6:
            raise ValueError('性格或追求建议格式无效。')
        insights[name] = []
        for row in rows:
            if not isinstance(row, dict): raise ValueError('性格或追求建议格式无效。')
            text, ids = row.get('text'), row.get('evidenceIds')
            if not isinstance(text, str) or not text.strip() or len(text) > 1200:
                raise ValueError('性格或追求建议说明无效。')
            if not isinstance(ids, list) or not ids or len(ids) > 12 or any(type(i) is not int or i not in {r['entryId'] for r in checked} for i in ids):
                raise ValueError('性格或追求建议缺少已核对的原文依据。')
            if name == 'personality' and not any(r['entryId'] in ids and r['speaker'] == '对方' for r in checked):
                raise ValueError('对方性格分析必须引用对方原文。')
            insights[name].append({'text': text, 'evidenceIds': ids})
    subject = '我' if perspective == 'self' else '对方'
    sufficient = {e.message.speaker for e in entries} >= {'我','对方'} and any(r['speaker']==subject for r in checked)
    if not sufficient:
        uncertainties = uncertainties + [f'缺少可核对的{subject}证据或双方对话，本批增减为0。']
    return {'rawDelta':delta, 'confidence':confidence, 'summary':summary, 'evidence':checked,
            'uncertainties':uncertainties, 'sufficient':sufficient, **insights}


class AffinityStore:
    def __init__(self, archive, perspective='other'):
        if perspective not in ('other', 'self'): raise ValueError('分析视角无效。')
        self.perspective = perspective
        self.prefix = 'affinity' if perspective == 'other' else 'self_affinity'
        self.archive = archive
        with archive.connection() as db:
            db.executescript(f'''
            CREATE TABLE IF NOT EXISTS {self.prefix}_batches(
                id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, before_score REAL NOT NULL,
                delta REAL NOT NULL, after_score REAL NOT NULL, result_json TEXT NOT NULL,
                model TEXT NOT NULL, created_at TEXT NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS {self.prefix}_targets(
                message_seq INTEGER PRIMARY KEY, batch_id TEXT NOT NULL,
                FOREIGN KEY(message_seq) REFERENCES messages(seq) ON DELETE CASCADE,
                FOREIGN KEY(batch_id) REFERENCES {self.prefix}_batches(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS {self.prefix}_stages(
                stage_key TEXT PRIMARY KEY, profile_id TEXT NOT NULL, result_json TEXT NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE);
            ''')

    def pending(self, profile, entries):
        with self.archive.connection() as db:
            used = {r[0] for r in db.execute(f'SELECT t.message_seq FROM {self.prefix}_targets t JOIN {self.prefix}_batches b ON t.batch_id=b.id WHERE b.profile_id=?',(profile,))}
        return [e for e in entries if e.id not in used]

    def view(self, profile, entries=None):
        self.archive.profile(profile)
        with self.archive.connection() as db:
            rows = db.execute(f'SELECT * FROM {self.prefix}_batches WHERE profile_id=? ORDER BY rowid',(profile,)).fetchall()
            count = db.execute(f'SELECT COUNT(*) FROM {self.prefix}_targets t JOIN {self.prefix}_batches b ON t.batch_id=b.id WHERE b.profile_id=?',(profile,)).fetchone()[0]
        batches = [{'id':r['id'],'before':r['before_score'],'delta':r['delta'],'after':r['after_score'],
                    'createdAt':r['created_at'],'model':r['model'],**json.loads(r['result_json'])} for r in rows]
        pending = len(self.pending(profile, self.archive.entries(profile) if entries is None else entries))
        return {'score':rows[-1]['after_score'] if rows else 50,'initial':50,'processed':count,
                'pending':pending,'availableBatches':pending//100,'batches':batches,'perspective':self.perspective}

    def stage(self, key):
        with self.archive.connection() as db:
            row = db.execute(f'SELECT result_json FROM {self.prefix}_stages WHERE stage_key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_stage(self, profile, key, result):
        with self.archive.connection() as db:
            db.execute(f'INSERT OR IGNORE INTO {self.prefix}_stages VALUES(?,?,?)',(key,profile,json.dumps(result,ensure_ascii=False,allow_nan=False)))

    def commit(self, profile, entries, result, model):
        if len(entries)!=100 or len({e.id for e in entries})!=100: raise ValueError('好感度每批必须为100条不同消息。')
        result = validate_result(result, entries, self.perspective)
        batch_id = hashlib.sha256(json.dumps([profile,[e.id for e in entries]]).encode()).hexdigest()
        with self.archive.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute(f'SELECT 1 FROM {self.prefix}_batches WHERE id=?',(batch_id,)).fetchone(): return False
            for e in entries:
                if not db.execute('SELECT 1 FROM messages WHERE seq=? AND profile_id=?',(e.id,profile)).fetchone(): raise ValueError('好感度批次不属于当前联系人。')
                if db.execute(f'SELECT 1 FROM {self.prefix}_targets WHERE message_seq=?',(e.id,)).fetchone(): raise ValueError('好感度消息已计入，请重新载入。')
            row = db.execute(f'SELECT after_score FROM {self.prefix}_batches WHERE profile_id=? ORDER BY rowid DESC LIMIT 1',(profile,)).fetchone()
            before = row[0] if row else 50
            raw = result['rawDelta'] * result['confidence'] if result['sufficient'] else 0
            delta = round(raw * min(1,(100-before)/50 if raw>=0 else before/50),1)
            after = round(max(0,min(100,before+delta)),1)
            db.execute(f'INSERT INTO {self.prefix}_batches VALUES(?,?,?,?,?,?,?,?)',(
                batch_id,profile,before,round(after-before,1),after,json.dumps(result,ensure_ascii=False,allow_nan=False),model,datetime.now(timezone.utc).isoformat()))
            db.executemany(f'INSERT INTO {self.prefix}_targets VALUES(?,?)',[(e.id,batch_id) for e in entries])
        return True
