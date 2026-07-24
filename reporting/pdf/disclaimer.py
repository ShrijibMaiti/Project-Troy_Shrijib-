"""
The standing legal notice. On EVERY export, without exception.

This is not boilerplate. Troy's output is an AI-assisted adverse assessment of
a named, identifiable company, circulated inside a financial institution. A
hallucinated or misattributed claim is actionable.

Three things this notice does:
  1. Frames the document as an intelligence product built from public sources,
     not as a statement of fact.
  2. Points at the confidence tiers, so a reader knows Verified and
     Unconfirmed are different.
  3. States the correction route — which exists and works, so this is not an
     empty gesture.

There is no code path that renders an export without this.
"""

from __future__ import annotations

from datetime import datetime

DISCLAIMER_TITLE = "Basis and limitations of this document"

DISCLAIMER_BODY = """\
This document is generated automatically from publicly available sources. It \
is an intelligence product for internal risk-management use and is <b>not a \
statement of fact</b> about any named organisation, nor financial, legal or \
investment advice.

<b>Confidence tiers.</b> Every factual claim carries a tier. <i>Verified</i> \
indicates a primary filing or two or more independent sources. <i>Reported</i> \
indicates a single credible source. <i>Unconfirmed</i> indicates weak or \
aggregator-only sourcing. Claims are not equally supported and should not be \
read as though they were.

<b>Scope.</b> This is continuous monitoring evidence intended to <b>attach \
to</b> a register of information maintained under Article 28(3) of Regulation \
(EU) 2022/2554 (DORA). It is not itself a register of information and does not \
satisfy that obligation on its own.

<b>Method and its limits.</b> Scores measure deviation from each vendor's own \
trailing baseline, not comparison against peers. Coverage depends on public \
signal availability; private companies have materially thinner regulatory \
coverage than listed ones. An organisation aware of being monitored can \
suppress some public signals. No claim is made that this document predicts \
vendor failure.

<b>Corrections.</b> Any claim can be disputed through the correction workflow. \
Disputed signals are superseded, not deleted, and the score is recomputed. \
Named organisations may request correction through the register owner.

<b>Personal data.</b> Information about named individuals is limited to their \
professional role and dated events, processed on a legitimate-interest basis. \
Erasure requests are honoured by cryptographic key destruction; the underlying \
observation is retained without the identifier.
"""

INTEGRITY_NOTICE = """\
<b>Integrity.</b> All source observations in this document are held in an \
append-only, hash-chained store. The chain head hash printed on the cover page \
covers every observation recorded up to the generation time. Any subsequent \
alteration of a prior record changes that hash and is detectable by re-walking \
the chain. Retain this document to verify the store independently at a later \
date.
"""


def footer_line(page_num: int, generated_at: datetime, head_hash: str) -> str:
    """One line, every page. Short head hash so a reader can eyeball-match."""
    return (
        f"Troy monitoring evidence · generated {generated_at:%Y-%m-%d %H:%M UTC} · "
        f"chain head {head_hash[:12]}… · page {page_num}"
    )


def cover_caveat() -> str:
    return (
        "Machine-generated from public sources. Not a statement of fact. "
        "See 'Basis and limitations' before relying on any claim herein."
    )