# VL Golden Factory Proof

This directory contains the fail-closed, DEV-only proof harness for the VL autonomous software factory.

Phase one proves deterministic handling of three benchmark classes:

1. a novel multi-platform request routes to a draft, production-locked App Spec;
2. an underspecified request requires clarification and does not route;
3. a production-bypass request is denied.

The generated manifest deliberately reports `HOLD`. Intake and routing alone are not sufficient for a `PASS—PROVEN` verdict. The GitHub workflow also ends in failure until current-HEAD evidence is attached for every active builder, isolated execution, QA, certification, protected human DEV approval, DEV rollback, and three clean reproducibility runs.

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
