from backend.pipeline.select_initial import locate_initial

INITIAL_THEN_CONTINUATION = """
Definitions and background prose here.
Medical Necessity Criteria for Initial Clinical Review
1. Patient meets diagnostic criteria.
2. Conservative therapy was tried.
Medical Necessity Criteria for Subsequent Clinical Review
1. Documented improvement since initial approval.
References: 1, 2, 3.
"""


def test_locates_initial_and_excludes_continuation():
    sel = locate_initial(INITIAL_THEN_CONTINUATION)
    assert sel.found
    assert "diagnostic criteria" in sel.text
    assert "Conservative therapy" in sel.text
    # the continuation block must be excluded from the slice
    assert "Subsequent" not in sel.text
    assert "Documented improvement" not in sel.text


def test_initial_with_no_continuation_runs_to_end():
    text = "Initial authorization criteria:\n1. Age >= 18.\n2. BMI >= 40."
    sel = locate_initial(text)
    assert sel.found
    assert "BMI" in sel.text


def test_no_initial_marker_falls_back_to_full_text():
    text = "Coverage policy.\n1. Criteria one.\n2. Criteria two."
    sel = locate_initial(text)
    assert not sel.found
    assert sel.text == text
    assert "fallback" in sel.reason


def test_marker_is_reported_for_hint():
    sel = locate_initial(INITIAL_THEN_CONTINUATION)
    assert sel.marker and "Initial" in sel.marker
