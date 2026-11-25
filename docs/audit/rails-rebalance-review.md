# Review: rails rebalance (9037611), 2026-11-25, code-reviewer, read-only

No P0 or P1. Checked clean: moved widgets keep names and handlers; `project_meter` is built before
any refresh; collapsed Model updates still shows its count in the pill; left rail at 1000x600 fits
without a scrollbar (list gets 213px).

- P2 user docs said "right rail" for Learning Centre and Run Log (README 41, 2824, 3608;
  `docs/learn/modules/17-troubleshooting.md:106`, `10-navigate.md:21`) and the `build_left_panel`
  docstring said "navigation lives in the header". **Fixed** in the follow-up commit.
- P3 placement test did not check order. **Fixed** (`test_the_moved_rows_keep_the_order_the_spec_gives_them`).
- P3 no test that the count pill shows while collapsed. **Fixed**
  (`test_a_collapsed_model_updates_section_still_shows_its_count`).
- P3 no test of the project meter's show/hide on the left rail. **Deferred**: the show/hide code
  in `main.py` is unchanged by the move; only its parent changed.
