from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen


API = "https://api.github.com/repos/lundus88/fieldgis-reference"


def get_json(url: str, token: str) -> dict:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "vl-golden-factory-proof",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise AssertionError("GITHUB_TOKEN is required for independent run verification")

    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    tested_sha = evidence["tested_sha"]
    verified = []
    for expected in evidence["runs"]:
        run_id = int(expected["run_id"])
        run = get_json(f"{API}/actions/runs/{run_id}", token)
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            raise AssertionError(f"run {run_id} did not complete successfully")
        if run.get("head_sha") != tested_sha:
            raise AssertionError(f"run {run_id} SHA mismatch")
        jobs_payload = get_json(f"{API}/actions/runs/{run_id}/jobs?per_page=100", token)
        jobs = {job["name"]: job for job in jobs_payload.get("jobs", [])}
        for job_name in expected["required_jobs"]:
            job = jobs.get(job_name)
            if not job or job.get("conclusion") != "success":
                raise AssertionError(f"run {run_id} missing successful job: {job_name}")
        successful_steps = {
            step["name"]
            for job in jobs.values()
            for step in job.get("steps", [])
            if step.get("conclusion") == "success"
        }
        missing_steps = sorted(set(expected["required_steps"]) - successful_steps)
        if missing_steps:
            raise AssertionError(f"run {run_id} missing successful steps: {missing_steps}")
        verified.append(
            {
                "run_id": run_id,
                "proof": expected["proof"],
                "head_sha": tested_sha,
                "html_url": run["html_url"],
                "status": "PASS",
                "verified_jobs": expected["required_jobs"],
                "verified_steps": expected["required_steps"],
            }
        )

    output = {
        "schema_version": "vl.verified-dev-sandbox-evidence/1",
        "status": "PASS",
        "tested_sha": tested_sha,
        "production_mutation": False,
        "verified_runs": verified,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "tested_sha": tested_sha, "run_count": len(verified)}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
