from datetime import date


def _norm(value):
    return (value or "").upper().replace("_", "-")


def validate(live_entries, conversion_items, today=None):
    if today is None:
        today = date.today()

    findings = []
    downstream = {_norm(item.get("id")): item for item in conversion_items}

    for entry in live_entries:
        entry_id = _norm(entry.get("id"))
        closing = entry.get("closing_date")
        status = entry.get("status")
        is_historical = status == "WATCHLIST"
        is_active = False
        if closing and not is_historical:
            try:
                is_active = date.fromisoformat(closing) >= today
            except ValueError:
                findings.append({"severity": "HOLD", "type": "INVALID_DATE", "id": entry.get("id")})
                continue

        match = downstream.get(entry_id)
        if match is None:
            # Allow stage-specific aliases for known naming differences by comparing meaningful suffixes.
            candidates = [item for key, item in downstream.items() if key.endswith(entry_id.split("-", 1)[-1]) or entry_id.endswith(key.split("-", 1)[-1])]
            match = candidates[0] if len(candidates) == 1 else None

        if is_active and match is None:
            findings.append({
                "severity": "HOLD",
                "type": "ACTIVE_SIGNAL_MISSING_CONVERSION",
                "id": entry.get("id"),
            })
            continue

        if match is not None:
            downstream_status = match.get("status")
            if status in {"HOLD", "WATCHLIST"} and downstream_status not in {"HOLD", "WATCHLIST"}:
                findings.append({
                    "severity": "HOLD",
                    "type": "GOVERNANCE_STATE_WIDENED",
                    "id": entry.get("id"),
                })

            active_until = match.get("active_until")
            if closing and active_until and closing != active_until:
                findings.append({
                    "severity": "REVIEW",
                    "type": "DATE_MISMATCH",
                    "id": entry.get("id"),
                    "upstream": closing,
                    "downstream": active_until,
                })

    return findings
