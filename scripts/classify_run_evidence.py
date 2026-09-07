#!/usr/bin/env python3
"""Classify saved GitHub run/job/artifact readbacks; never dispatch or accept domain work."""
import argparse
import json
import re
from datetime import datetime


def classify(payload):
    def result(status, reason):
        return {"status": status, "reason": reason, "domain_accepted": False}
    if not isinstance(payload, dict):
        return result("invalid", "evidence must be an object")
    expected, run, listing = (payload.get(k) for k in ("expected", "run", "jobs"))
    if not all(isinstance(v, dict) for v in (expected, run, listing)):
        return result("invalid", "expected, run and jobs objects are required")
    sha = expected.get("head_sha")
    names = expected.get("job_names")
    workflow = expected.get("workflow_path")
    if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha) or not isinstance(workflow, str) or not workflow.startswith(".github/workflows/"):
        return result("invalid", "exact expected revision and workflow are required")
    if not isinstance(names, list) or not names or not all(isinstance(n, str) and n.strip() for n in names) or len(names) != len(set(names)):
        return result("invalid", "non-empty unique required job names are required")
    if not isinstance(run.get("path"), str) or any(type(run.get(k)) is not int or run[k] <= 0 for k in ("id", "run_attempt")):
        return result("invalid", "run path, positive run ID and run attempt are required")
    if run.get("head_sha") != sha or run["path"].split("@", 1)[0] != workflow:
        return result("stale", "run does not match expected revision/workflow")
    if run.get("status") != "completed":
        return result("pending", "run has not completed")
    jobs = listing.get("jobs")
    if not isinstance(jobs, list) or type(listing.get("total_count")) is not int or listing["total_count"] != len(jobs) or not all(isinstance(j, dict) for j in jobs):
        return result("incomplete", "complete paginated jobs readback is required")
    if not jobs:
        return result("blocked", "no job execution evidence")
    selected = []
    for name in names:
        matches = [j for j in jobs if j.get("name") == name]
        if len(matches) != 1:
            return result("incomplete", "required job missing or ambiguous")
        job = matches[0]
        if type(job.get("run_attempt")) is not int or job.get("run_id") != run["id"] or job.get("head_sha") != sha or job.get("run_attempt") != run["run_attempt"]:
            return result("stale", "job revision/run/attempt does not match")
        steps = job.get("steps")
        if not job.get("runner_id") or not isinstance(steps, list) or not steps:
            return result("blocked", "required job did not produce runner/step evidence; cause unknown")
        if job.get("status") != "completed":
            return result("pending", "required job has not completed")
        if job.get("conclusion") != "success" or not all(isinstance(s, dict) for s in steps) or any(s.get("conclusion") in {"failure", "cancelled", "timed_out"} for s in steps) or not any(s.get("conclusion") == "success" for s in steps):
            return result("failed", "required job did not succeed")
        selected.append(job)
    if run.get("conclusion") != "success":
        return result("failed", "run did not succeed")
    required_artifacts = expected.get("artifact_names", [])
    if not isinstance(required_artifacts, list) or not all(isinstance(n, str) and n.strip() for n in required_artifacts):
        return result("invalid", "artifact_names must be a string list")
    if required_artifacts:
        artifacts = payload.get("artifacts", {})
        items = artifacts.get("artifacts") if isinstance(artifacts, dict) else None
        if not isinstance(items, list) or artifacts.get("total_count") != len(items):
            return result("incomplete", "complete artifact readback is required")
        for name in required_artifacts:
            matches = [a for a in items if isinstance(a, dict) and a.get("name") == name and a.get("expired") is False]
            if len(matches) != 1:
                return result("incomplete", "required artifact missing, expired or ambiguous")
            origin = matches[0].get("workflow_run", {})
            if not isinstance(origin, dict):
                return result("incomplete", "artifact run provenance is missing")
            if origin.get("id") != run["id"] or origin.get("head_sha") != sha:
                return result("stale", "artifact does not match run/revision")
            if "run_attempt" in origin and origin["run_attempt"] != run["run_attempt"]:
                return result("stale", "artifact does not match run attempt")
            if run["run_attempt"] > 1:
                try:
                    created = datetime.fromisoformat(matches[0]["created_at"].replace("Z", "+00:00"))
                    started = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
                    if created.tzinfo is None or started.tzinfo is None:
                        raise ValueError("timezone required")
                except (KeyError, ValueError, TypeError, AttributeError):
                    return result("incomplete", "rerun artifact requires creation/start timestamps")
                if created < started:
                    return result("stale", "artifact predates the current run attempt")
    return result("execution_verified", "matched completed run, required jobs and artifact metadata; owner must inspect result contents")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as stream:
        output = classify(json.load(stream))
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if output["status"] == "execution_verified" else 1)
