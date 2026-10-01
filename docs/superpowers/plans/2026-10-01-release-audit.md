# chat1 v2.6 Release Audit Plan

> Execute inline with Superpowers systematic debugging, TDD and verification-before-completion. Request one independent whole-change review after the fixes.

**Goal:** Correct reproducible bugs in the current GitHub release without replacing the existing application.

**Architecture:** Keep the existing JSON readers and SQLite transactional checkpoints. Preserve successfully received scoring subgroups if a subsequent request fails; skip empty/media-only child conversations while retaining validation of malformed input.

**Tech Stack:** Python 3.12, tkinter, SQLite, PyInstaller, Windows x64.

**Spec:** Current user request: download the latest repository version, inspect and correct its bugs; do not check the GitHub 404 issue; do not show test windows or confirmation dialogs. Earlier requirements: persist scoring progress without loss or repeated completed requests, import text only, preserve personal settings and records, deliver the portable application and keep GitHub updated.

## Constraints

- Base commit: de518eda8f31c180840bbac85793ccc08718ada9, tag v2.6.0.
- Use synthetic records and mocked model endpoints, with no private-data writes or real model charges.
- Run UI verification on an isolated Windows desktop that is never activated.
- Preserve the latest release files and clean dependencies; publish a new patch release only after verification.

## Review Focus

- First subgroup failure must retain the original error and create no empty save.
- Partial successes must be visible, durable, and omitted from subsequent resume requests.
- Cancellation and oversized text must preserve received subgroups.
- Empty/media-only child conversations must not hide valid neighbours; malformed children still fail clearly.
- Portable tools, fonts and app startup must work after full extraction with fresh user directories.

## Tasks

1. Add failing tests in `tests/test_batch.py` for later-subrequest network failure and cancellation after partial receipt. Modify `chat_assistant/history_runner.py` to save received rows before propagating the next request error, including normal progress events. Verify reopening and resuming the real SQLite store.
2. Add failing import tests for session arrays, conversation arrays and ChatLab JSONL blocks mixed with empty/media-only histories. Modify `chat_assistant/importers.py` so child parsing can yield no text, while the overall file still rejects all-empty input and malformed structures.
3. Run the complete suite with the release's clean bundled tools in the isolated desktop; investigate reproducible failures. Review the diff independently. Build a patched EXE, verify extracted portable startup and checksums, update the local delivery and GitHub patch release.

## Evidence

- Repository source and original portable ZIP/standalone EXE downloaded and SHA256 checked.
- Initial visible baseline: 96 tests, 3 failures/2 errors/1 skip. Launcher failure is absent optional tools in source checkout; import failures follow a transient teardown error. Two focused tests passed in isolated desktop. Full hydrated hidden baseline pending.
- JSON media-only child blocks valid neighbour import: reproduced with `from_json({'sessions': [media, valid]})`, fails in `_finish` before the valid child is read.

- Scoring/import regressions: RED observed; 28 core tests GREEN after child-validation review fix.
- Independent review: no critical issue; malformed child validation finding reproduced with 6 failing cases and corrected. The stale test-count minor was corrected to 99 passed / 2 skipped.
- Final functional suite: 101 tests, 99 passed, 2 environmental framebuffer skips; no real API calls.
- Verification scope: two visible-framebuffer tests were not executed, preserving the explicit no-popups request. Hidden GUI checks cover other navigation, dates, fonts, guide and import actions. Abrupt termination before receiving/saving a complete response remains subject to the documented retry behavior.
