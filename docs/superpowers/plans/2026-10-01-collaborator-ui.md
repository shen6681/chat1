# Connect the collaborator UI to the existing desktop core

User chose to retain Yangfan Hu's UI and connect real import, scoring and settings.
Base: UI 81d5305; merge main a569222 so previous durable-checkpoint fixes remain.

1. Reproduce static/demo behavior and package/CLI failures. Add failing integration tests.
2. Add a loopback-only, per-session authenticated local API reusing ArchiveStore,
   SettingsStore, existing readers and run_history. No browser key/chat persistence.
3. Replace mock UI actions with real import preview/identity confirmation, paged
   archive/time filtering, ten-message jobs with pause/resume, explicit explanations,
   real connection checks and encrypted settings. Keep the collaborator's visual design.
4. Preserve native screen/OCR, database mapping and export-tool workflows through
   an explicit native-workspace entry. Remove simulated success claims.
5. Include web/dist in the EXE; preserve self-test and legacy CLI routing. Validate
   Python regression suite, web build, synthetic HTTP flows, browser interaction,
   packaged startup and clean ZIP. Preserve personal state and collaborator branch.
6. Build v2.7.0 locally, sync source/delivery/clean ZIP and publish reviewed integration
   to main without replacing or force-pushing the collaborator's UI branch.

Acceptance: imported file text appears verbatim, media ignored, choosing self works;
rating state reflects saved SQLite rows, failed requests do not show success; previous
keys are retained when password fields are untouched; no mock profiles on fresh start;
cross-origin clients cannot access local API or secrets; fresh unpacked EXE serves UI.
