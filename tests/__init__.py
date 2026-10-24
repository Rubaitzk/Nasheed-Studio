"""
Regression tests – Phase 1 bug fixes.

test_layout.py       Bug A: long filenames must not stretch the left panel.
test_selection.py    Bug B: list-widget selected text must be readable.
test_export_job.py   Bug C: process lifecycle – cancel, app-shutdown, failure.
test_duplicate.py    Bug C: duplicate-export guard + UI returns to idle.

Run all:
    python -m pytest tests/ -v
"""
