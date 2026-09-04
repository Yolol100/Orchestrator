#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_CORE = {
    "Yolol100/Orchestrator",
    "Yolol100/Designchecker",
    "Yolol100/seochecker",
    "Yolol100/elementorjson",
    "Yolol100/programmeren",
    "Yolol100/wordpressconnector",
    "Yolol100/transcriberen",
}
EXPECTED_EXCLUDED = {"Yolol100/Leadscanner", "Yolol100/vacature-engine"}
FORBIDDEN_ACTIVE = {
    "Yolol100/Checklist",
    "Yolol100/Elementorconnector",
    "Yolol100/Export-acf-to-csv",
    "Yolol100/elementor-design-kit-generator",
    "Yolol100/Woocommerce-return-requests",
}
ALLOWED_CONSOLIDATION_STATUS = {"migration", "duplicate-deprecation"}


def validate(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    if data.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    if data.get("controller") != "webactueel-workflow":
        errors.append("controller must be webactueel-workflow")

    core = data.get("core_repositories")
    if not isinstance(core, list):
        return errors + ["core_repositories must be an array"]
    core_repos = [item.get("repository") for item in core if isinstance(item, dict)]
    if len(core_repos) != len(set(core_repos)):
        errors.append("core repositories must be unique")
    if set(core_repos) != EXPECTED_CORE:
        errors.append("core repository set differs from the seven-repository platform contract")
    if set(core_repos) & FORBIDDEN_ACTIVE:
        errors.append("consolidation/deprecated/archive repository is active core")
    for item in core:
        if not isinstance(item, dict):
            errors.append("core entry must be an object")
            continue
        for field in ("id", "repository", "owner_skill", "role", "status"):
            if not item.get(field):
                errors.append(f"core entry missing {field}: {item!r}")
        if item.get("status") != "active":
            errors.append(f"core repository is not active: {item.get('repository')}")

    consolidations = data.get("consolidations")
    if not isinstance(consolidations, list):
        errors.append("consolidations must be an array")
        consolidations = []
    seen_sources: set[str] = set()
    for item in consolidations:
        if not isinstance(item, dict):
            errors.append("consolidation entry must be an object")
            continue
        source = item.get("source")
        target = item.get("target")
        if source in seen_sources:
            errors.append(f"duplicate consolidation source: {source}")
        seen_sources.add(source)
        if target not in EXPECTED_CORE and target != "Yolol100/ACF-Text-Manager":
            errors.append(f"unknown consolidation target: {target}")
        if source in EXPECTED_CORE:
            errors.append(f"active core cannot be a consolidation source: {source}")
        if item.get("status") not in ALLOWED_CONSOLIDATION_STATUS:
            errors.append(f"invalid consolidation status: {source}")
        if not item.get("remove_after"):
            errors.append(f"consolidation lacks exit gates: {source}")

    excluded = data.get("excluded_repositories")
    if not isinstance(excluded, list):
        errors.append("excluded_repositories must be an array")
        excluded = []
    excluded_repos = {item.get("repository") for item in excluded if isinstance(item, dict)}
    if excluded_repos != EXPECTED_EXCLUDED:
        errors.append("excluded repository set must remain Leadscanner plus vacature-engine")
    if excluded_repos & set(core_repos):
        errors.append("excluded repository may not be active core")

    all_classified: list[str] = list(core_repos)
    all_classified += [item.get("source") for item in consolidations if isinstance(item, dict)]
    all_classified += [
        item.get("repository")
        for key in ("deprecated_repositories", "archive_candidates", "excluded_repositories")
        for item in data.get(key, [])
        if isinstance(item, dict)
    ]
    classified = [item for item in all_classified if item]
    if len(classified) != len(set(classified)):
        errors.append("a repository appears in more than one primary class")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=Path("config/platform-repositories.json"))
    args = parser.parse_args()
    data = json.loads(args.path.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        print("PLATFORM ARCHITECTURE: FAIL")
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print("PLATFORM ARCHITECTURE: PASS (7 core repositories; excluded repositories unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
