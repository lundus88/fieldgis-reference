# VL Golden Factory Proof

This directory contains the fail-closed, DEV-only proof harness for the VL autonomous software factory.

Phase one proves deterministic handling of three benchmark classes:

1. a novel multi-platform request routes to a draft, production-locked App Spec;
2. an underspecified request requires clarification and does not route;
3. a production-bypass request is denied.

The generated manifest deliberately reports `HOLD`. Intake and routing alone are not sufficient for a `PASS—PROVEN` verdict. The GitHub workflow also ends in failure until current-HEAD evidence is attached for every active builder, isolated execution, QA, certification, protected human DEV approval, DEV rollback, and three clean reproducibility runs.

`dev-sandbox-evidence.json` records the six DEV-only GitHub runs used for the active-builder and isolation baseline. The workflow does not trust this declaration by itself: `verify_dev_sandbox_evidence.py` reads each run and its jobs from the GitHub API, requires the exact tested SHA, and checks that named substantive steps completed successfully.

## Local phase-one check

```bash
python3 vl/proof/run_golden_factory_benchmark.py \
  --cases vl/proof/golden-benchmark-cases.json \
  --output golden-factory-manifest.json \
  --source-sha "$(git rev-parse HEAD)"

python3 vl/proof/verify_golden_factory_manifest.py \
  golden-factory-manifest.json \
  --expected-sha "$(git rev-parse HEAD)"
```

This command writes only a local evidence file. It does not contact or mutate production.
