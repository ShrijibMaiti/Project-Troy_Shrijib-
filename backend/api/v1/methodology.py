"""
The credibility screen.

Serves the calibration Wrik's notebooks produce — weights, thresholds, and the
LEAD-TIME DISTRIBUTION from the backtest. That chart answers the only question
that matters ("did the score move before real deterioration events?") and it
belongs in the product, not just the pitch deck.

Limitations are served alongside, not hidden. Stating them is the honesty that
makes the rest credible.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.deps import CurrentOrg
from backend.schemas import MethodologyOut

router = APIRouter(prefix="/methodology", tags=["methodology"])

ENGINE_VERSION = "0.1.0"

LIMITATIONS = [
    "Public-signal monitoring only. A vendor aware of being scored can suppress "
    "some signals; weighting favours hard-to-suppress sources (court dockets, "
    "regulatory filings, job-posting removals).",
    "Private companies have no SEC coverage. The private-company source tier "
    "(Form D, CourtListener, Companies House, Crunchbase) is thinner than "
    "public-company coverage.",
    "Scores are relative to each vendor's own trailing baseline, not to peers. "
    "A high score means unusual for THIS vendor.",
    "Backtest evidence is directional, not statistical. The current event set is "
    "too small to support any claim about lead time or precision.",
    "This is monitoring evidence that attaches to an Article 28(3) register. "
    "It is not itself a register of information.",
]


@router.get("", response_model=MethodologyOut)
async def methodology(org: CurrentOrg) -> MethodologyOut:
    weights = settings.load_calibration("weights")
    thresholds = settings.load_calibration("thresholds")
    lead_time = settings.load_calibration("lead_time")
    # Raw per-day score series from the backtest. Served so the UI can plot the
    # actual curves rather than a summary — the reader should see that the
    # control tracks the failure case, not be told it.
    series = settings.load_calibration("backtest_series")
    return MethodologyOut(
        weights=weights,
        thresholds=thresholds,
        lead_time=lead_time,
        backtest_series=series,
        calibrated=bool(weights and thresholds),
        limitations=LIMITATIONS,
        engine_version=ENGINE_VERSION,
    )