# Generated-code isolation fixture

This fixture is intentionally hostile. The certification workflow executes it inside the same sandbox used by the active factory build boundary and requires credential absence, denied network egress, denied parent/cross-run writes, bounded process creation, and a bounded wall clock. A structural check alone is not PASS evidence.
