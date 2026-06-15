"""Initial-only selection heuristic.

These Oscar guidelines often contain an *Initial* criteria tree followed by a
*Continuation* (a.k.a. subsequent / reauthorization / renewal / maintenance) tree,
and sometimes multiple indication pathways. We must structure only the **initial**
criteria.

This module locates the initial-criteria region deterministically. It is used two
ways by the structuring pipeline:
  1. As a focused **hint** appended to the LLM prompt (the model still extracts from
     the full document — chosen "LLM-driven" approach).
  2. As the **fallback signal**: if no initial marker is found, we tell the model to
     fall back to the first complete criteria tree.

Failure modes (documented):
  - A document that leads with continuation criteria, or labels its initial section
    with unusual wording, may yield a wrong/empty hint -> we then rely on the LLM and
    the "first complete tree" fallback.
  - Marker words appearing in prose (not as a heading) can mis-locate the boundary;
    we take the *first* initial marker and the *next* continuation marker after it,
    which is robust for the common "Initial ... Subsequent ..." layout.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Ordered by specificity. Matched case-insensitively.
INITIAL_MARKERS = [
    r"medical necessity criteria for initial",
    r"initial clinical review",
    r"initial (?:authorization|approval|review|request|criteria|treatment)",
    r"\binitial\b",
]
CONTINUATION_MARKERS = [
    r"subsequent clinical review",
    r"medical necessity criteria for (?:subsequent|continued|continuation)",
    r"\bcontinuation\b",
    r"\bsubsequent\b",
    r"\breauthorization\b",
    r"\bre-authorization\b",
    r"\brenewal\b",
    r"continued care",
    r"maintenance therapy",
]


@dataclass
class InitialSelection:
    found: bool
    text: str          # the located initial slice, or full text on fallback
    marker: str | None  # the matched initial header (for the LLM hint)
    reason: str


def _first_match(patterns: list[str], text: str, start: int = 0):
    best = None
    for pat in patterns:
        m = re.compile(pat, re.IGNORECASE).search(text, start)
        if m and (best is None or m.start() < best.start()):
            best = m
    return best


def locate_initial(text: str) -> InitialSelection:
    init = _first_match(INITIAL_MARKERS, text)
    if not init:
        return InitialSelection(
            found=False,
            text=text,
            marker=None,
            reason="no initial marker found; fallback to first complete tree in full doc",
        )
    cont = _first_match(CONTINUATION_MARKERS, text, start=init.end())
    end = cont.start() if cont else len(text)
    return InitialSelection(
        found=True,
        text=text[init.start():end],
        marker=text[init.start():init.start() + 60].strip(),
        reason=(
            "sliced from initial marker to next continuation marker"
            if cont
            else "initial marker found; no continuation marker -> initial to end"
        ),
    )
