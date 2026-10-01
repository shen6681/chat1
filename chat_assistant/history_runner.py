"""Sequential archive analysis; successful results and checkpoints commit together."""
from __future__ import annotations

import uuid
from dataclasses import replace

from .history_analysis import analysis_signature, analyze_message, context_for
from .batch_analysis import analyze_batch, batch_context, checked_result, issue_result, UnjudgeableResponse


def run_history(store, settings, profile_id, entries=None, start_text="", end_text="", force=False,
                run_id=None, cancel=None, on_progress=None, batch_size=10):
    if type(batch_size) is not int or not 1 <= batch_size <= 10:
        raise ValueError("每组数量应为1到10。")
    (replace(settings,mode="TypeSafe Jev") if batch_size>1 and settings.mode!="DeepSeek" else settings).validate()
    owner = uuid.uuid4().hex
    if not store.acquire_analysis(profile_id, owner):
        raise ValueError("另一个程序或任务正在分析这个联系人，已阻止重复请求。请等待或暂停那个任务。")
    try:
        signature = analysis_signature(settings)
        if run_id:
            info = store.run_info(run_id)
            if info["profile_id"] != profile_id:
                raise ValueError("续做任务不属于当前联系人。")
            store.finish_run(run_id, "running")
        else:
            if not entries:
                raise ValueError("当前范围没有文字消息。")
            run_id = store.begin_run(profile_id, start_text, end_text, entries, signature, settings.mode, force)
        # Read the persisted snapshot rather than accidentally including newly imported messages.
        entries = store.run_entries(run_id)
        total = len(entries); completed = sum(e.done for e in entries)
        if on_progress:
            on_progress("started", {"run_id": run_id, "completed": completed, "total": total})
        try:
            pending = [i for i,e in enumerate(entries) if not e.done]
            for offset in range(0,len(pending),batch_size):
                positions = pending[offset:offset+batch_size]
                if cancel and cancel.is_set():
                    store.finish_run(run_id, "paused")
                    return {"run_id": run_id, "state": "paused", "completed": completed, "total": total}
                if not store.acquire_analysis(profile_id, owner):
                    raise ValueError("当前分析任务锁已改变，已停止发起请求。")
                request_error = None
                if batch_size==1:
                    entry = entries[positions[0]]
                    transcript = context_for(entries,positions[0])
                    context_hash = transcript.fingerprint
                    native = store.stage(entry.id,signature,context_hash)
                    result = analyze_message(settings,transcript,cancel,native=native,
                        save_native=lambda r:store.save_stage(entry.id,signature,context_hash,r))
                    results = [checked_result(entry.id,result)]
                else:
                    results = []
                    # Oversized individual text is a review item, not a reason to skip its neighbours.
                    groups, group, length = [], [], 0
                    for index in positions:
                        size = len(entries[index].message.text)+50
                        if size>10050:
                            results.append(issue_result(entries[index].id,"本条文字过长，已标记并继续其他记录。"))
                            continue
                        if group and length+size>32000:
                            groups.append(group);group=[];length=0
                        group.append(index);length+=size
                    if group: groups.append(group)
                    context_hash = "batch-v2"
                    for group in groups:
                        if cancel and cancel.is_set() and results:
                            break
                        try:
                            messages,targets,context_hash = batch_context(entries,group)
                            results.extend(analyze_batch(settings,messages,targets,cancel))
                        except UnjudgeableResponse as error:
                            results.extend(issue_result(entries[index].id,str(error)) for index in group)
                        except Exception as error:
                            if not results:
                                raise
                            # A later split request must not discard already received
                            # scores or cause those paid requests to repeat on resume.
                            request_error = error
                            break
                # The entire completed group is durable before any UI update, including pause requests.
                store.save_batch(profile_id,results,context_hash,signature,run_id)
                completed += len(results)
                for row in results:
                    entry = next(e for e in (entries[i] for i in positions) if e.id==row["entry_id"])
                    entry.rating = row["rating"] or entry.rating
                    entry.issue = row.get("issue"); entry.done = True
                if on_progress:
                    data = {"run_id":run_id,"results":results,"completed":completed,"total":total}
                    if batch_size==1:
                        on_progress("rated",{**data, "entry_id":entry.id,"rating":result})
                    else:
                        on_progress("batch",data)
                if request_error is not None:
                    raise request_error
                if cancel and cancel.is_set() and completed<total:
                    store.finish_run(run_id,"paused")
                    return {"run_id":run_id,"state":"paused","completed":completed,"total":total}
            store.finish_run(run_id, "completed")
            return {"run_id": run_id, "state": "completed", "completed": completed, "total": total}
        except Exception as error:
            state = "paused" if cancel and cancel.is_set() else "error"
            store.finish_run(run_id, state, str(error))
            if state == "paused":
                return {"run_id": run_id, "state": state, "completed": completed, "total": total}
            raise
    finally:
        store.release_analysis(profile_id, owner)
