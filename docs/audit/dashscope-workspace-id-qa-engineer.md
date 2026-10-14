# QA report: DashScope Workspace ID (Verify, loop 0, 2026-10-13)

Role: qa-engineer. Worktree code confirmed under test (`services.qwen_client.__file__` in `imprint-harden-ship`).
`QT_QPA_PLATFORM=offscreen`, imprint venv. Machine loaded by parallel runs (11-12 min per full run, not the documented 90 s).
Playbook `status: baseline`.

## Verdict: FAIL
New logic is well tested, but the diff introduces an order-dependent failure.

## 1. Full suite
| Run | Result |
|---|---|
| random order, attempt 1 | Aborted: faulthandler dump, likely the 300 s thread timeout under load |
| random order, attempt 2 | 1458 passed, 6 skipped, 6 subtests passed (660 s) |
| `-p no:randomly` | **1 failed**, 1457 passed, 6 skipped, 6 subtests passed (743 s) |

Failure: `tests/test_voice_and_rates.py::test_qwen_says_when_it_is_on_the_standard_host` at line 108
(`assert qwen_client.on_legacy_endpoint()`). Cause: the new `tests/test_settings_keys.py::test_workspace_id_field_explains_itself_and_never_blocks_save`
clicks Save; `apply` writes `DASHSCOPE_WORKSPACE_ID=ws1` into the real `os.environ` and nothing restores it. Reproduced with
`pytest -p no:randomly tests/test_settings_keys.py tests/test_voice_and_rates.py`: 1 failed, 44 passed. Fix: register
`DASHSCOPE_WORKSPACE_ID` and `DASHSCOPE_BASE_URL` with `monkeypatch` in the UI test so they are restored.

`tests/test_benchmarks_drift.py` did not fail in this run (local-differences test passed; sentinel drift case skipped).
`tests/test_theme.py` is slow under load, not hung (about 30 s alone).

## 2. Success measure to test
| Spec item | Test | Quality |
|---|---|---|
| `ws1` gives exact chat URL, empty note | `test_workspace_id_derives_chat_url` | Good |
| Hostile IDs never reach a URL | `test_hostile_workspace_ids_never_reach_a_url` (15 cases), `test_workspace_id_is_stripped_and_lowercased` | Good; gaps below |
| Settings shows an error | `test_workspace_id_field_explains_itself_and_never_blocks_save` | Real assertions; `qWait(600)`; leaks env |
| Byte-identical with no ID | `test_no_id_is_byte_identical` | Good |
| Explicit vars win; blank unset | `test_explicit_urls_win_and_blank_is_unset`, `test_video_base_strips_trailing_slash` | Good |
| Probe uses typed ID | `test_probe_uses_typed_workspace_id` | Weak: calls `prepare_probe` directly, not the dialog path |
| 401 hint | `test_workspace_401_hint` | Good |
| Image follows video resolver | `test_image_endpoint_uses_the_video_resolver` | Good |
| Save | `test_write_values_saves_workspace_id` | Good (0600, lines preserved) |

## 3. Mutation check (scratch copy only)
Killed: regex loosened (2 variants), precedence swapped, `_env` without strip, blank chat/video treated as set, video uses ID,
`workspace_auth_hint` always empty, 401 branch removed, validator without strip/lower.
**Survived:** M6 hint host check loosened to substring (existing negative is `evil.example/maas...`; real lookalike
`https://x.maas.aliyuncs.com.evil.com` unprobed); **M8** `typed_values_for` stops passing the typed ID to the probe (no dialog-level test).

## Ranked gaps
1. Env leak from the new UI test fails the existing endpoint test when run after it. **Blocks merge.**
2. M8: no test of the dialog's typed-ID-to-probe wiring.
3. No test for `on_probe_result` host labels or the invalid-ID-during-Test text.
4. Hostile table lacks a `ws1\n` reject case and an `xn--` case.
5. Fixed `qWait(600)` sleeps; slow, could flake under load.
6. Coverage not measured (no floor). By inspection the `qwen_client.py` changes are hit; `dialogs.py` probe-label branches are not.

---

# Verify loop 1 (2026-10-14): PASS

| Run | Result |
|---|---|
| full suite `-p no:randomly` | 1491 passed, 6 skipped, 6 subtests passed (18:47, load avg 40-158) |
| full suite `--randomly-seed=1` | 1491 passed, 6 skipped, 6 subtests passed (22:08) |
| 4 related files, seeds 2, 3, 12345 | 94 passed each |
| loop-0 blocker pair, fixed order | 78 passed (was 1 failed) |

`tests/test_benchmarks_drift.py`: local-differences test passed; Sentinel drift case and `test_converter_drift.py` SKIPPED
because the worktree has no Sentinel / lab_hub checkout beside it, so the known red card cannot show from here.

Success measure items 1-5: all met (see loop-0 table; item 5 now proven at dialog level by
`test_qwen_test_probes_the_typed_id_and_names_the_host`, real dialog and client, only `list_models_live` stubbed).
Loop-0 gaps 1-4 and 6 closed; gap 5 (fixed `qWait(600)`) open, low.

Mutation (copy only): M8, M6, N1b (invalid-ID note echoes raw value) KILLED. Survived, none blocking:
- **N5** `run_probe` drops `== 401`: any workspace-host error (500, timeout) would read as the 401 workspace hint. Add a case.
- **N2** `endpoint_warning` `endswith("aliyuncs.com")` without the dot: `https://evilaliyuncs.com/v1` not warned. Add a row.
- **N4** `on_probe_result` appends the host label on failure: failure path untested.
- **N3** `_base_url` interpolates the raw env value: no assertion for `" WS1 "`.

Changed-line coverage (settrace tracer, 4 files): statements 102/102; branch arms 44/46 (untaken: `services/api_keys.py:343`
false arm, `ui/dialogs.py:565` false arm).

Housekeeping: `docs/company/app-context.md` test counts are stale (says 1408 collected; now 1497 collected, 1491 pass).
