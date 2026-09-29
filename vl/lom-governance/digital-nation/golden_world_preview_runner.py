"""Synthetic Golden World Journey Preview runner.

This runner is intentionally non-production. It refuses to build a complete
journey while any required Digital Nation binding remains on HOLD.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, List

from golden_world_preflight import preview_preflight
from golden_world_transaction import validate_golden_world_transaction


def _event(n: int, event_type: str, **extra: Any) -> Dict[str, Any]:
    event = {
        "event_id": f"gw_evt_{n:02d}",
        "event_type": event_type,
        "occurred_at": f"2026-09-29T09:{n:02d}:00Z",
        "actor_id": "member_preview_001",
        "subject_id": "member_preview_001",
        "source_system": "lom-digital-nation-preview",
        "correlation_id": "golden_world_preview_001",
        "evidence_ref": f"evidence://preview/golden-world/{n}",
        "policy_version": "digital-nation-draft-v1",
        "authority_context": {"decision": "ALLOW", "claims": []},
    }
    event.update(extra)
    return event


def build_preview_events() -> List[Dict[str, Any]]:
    """Build a fully synthetic journey only for contract validation."""
    return [
        _event(1, "member.registered"),
        _event(2, "member.identity_verified", assurance_level="PREVIEW_FIXTURE"),
        _event(
            3,
            "skill.signal_verified",
            skill_id="skill_script_polish",
            verification_method="ASSESSMENT",
        ),
        _event(
            4,
            "opportunity.matched",
            opportunity_id="opp_preview_001",
            match_basis="verified_skill_fixture",
        ),
        _event(
            5,
            "offer.accepted",
            offer_id="offer_preview_001",
            terms_ref="terms://preview/offer/1",
        ),
        _event(
            6,
            "order.created",
            order_id="order_preview_001",
            buyer_id="buyer_preview_001",
            seller_id="member_preview_001",
            offer_id="offer_preview_001",
            amount=100,
            currency="MYR",
        ),
        _event(
            7,
            "payment.confirmed",
            order_id="order_preview_001",
            payment_reference_id="pay_preview_001",
            provider="sandbox-fixture",
            amount=100,
            currency="MYR",
            evidence_source="sandbox_signed_callback_fixture",
        ),
        _event(
            8,
            "delivery.submitted",
            order_id="order_preview_001",
            delivery_id="delivery_preview_001",
            seller_id="member_preview_001",
        ),
        _event(
            9,
            "delivery.accepted",
            order_id="order_preview_001",
            acceptance_id="accept_preview_001",
            buyer_id="buyer_preview_001",
        ),
        _event(
            10,
            "earning.recorded",
            order_id="order_preview_001",
            earning_id="earning_preview_001",
            beneficiary_id="member_preview_001",
            gross_amount=100,
            fees=10,
            net_amount=90,
            currency="MYR",
        ),
        _event(
            11,
            "reputation.updated",
            member_id="member_preview_001",
            reputation_event_id="rep_preview_001",
            reason_code="DELIVERY_ACCEPTED",
        ),
        _event(
            12,
            "referral.attributed",
            order_id="order_preview_001",
            referrer_id="member_preview_002",
            attribution_rule="preview-fixture-v1",
        ),
    ]


def run_synthetic_golden_world(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    preflight = preview_preflight(manifest)
    if preflight["decision"] != "READY_FOR_SYNTHETIC_GOLDEN_JOURNEY":
        return {
            "schema": "lom.digital-nation.golden-world-preview-run/1",
            "mode": "PREVIEW_SYNTHETIC_ONLY",
            "decision": "HOLD",
            "reason": "PREFLIGHT_NOT_READY",
            "preflight": preflight,
            "production_authority": False,
            "live_payment_authority": False,
            "live_payout_authority": False,
        }

    events = build_preview_events()
    validation = validate_golden_world_transaction(events)
    return {
        "schema": "lom.digital-nation.golden-world-preview-run/1",
        "mode": "PREVIEW_SYNTHETIC_ONLY",
        "decision": "PASS" if validation.ok else "FAIL",
        "validation_reasons": validation.reasons,
        "event_count": len(events),
        "correlation_id": validation.correlation_id,
        "production_authority": False,
        "live_payment_authority": False,
        "live_payout_authority": False,
        "real_customer_evidence": False,
        "real_revenue_evidence": False,
        "real_worker_evidence": False,
    }
