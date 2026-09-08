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
    "Yolol100/Leadscanner",
    "Yolol100/vacature-engine",
}
EXPECTED_OWNERS = {
    "Yolol100/Orchestrator": "webactueel-workflow",
    "Yolol100/Designchecker": "design",
    "Yolol100/seochecker": "seo",
    "Yolol100/elementorjson": "elementor",
    "Yolol100/programmeren": "wordpressqualityarchitect",
    "Yolol100/wordpressconnector": "wordpressqualityarchitect",
    "Yolol100/transcriberen": "webactueel-workflow",
    "Yolol100/Leadscanner": "leads",
    "Yolol100/vacature-engine": "vacature-search",
}
EXPECTED_CONSUMERS = {
    "Yolol100/Orchestrator": set(),
    "Yolol100/Designchecker": {"website-qa-checklist"},
    "Yolol100/seochecker": set(),
    "Yolol100/elementorjson": set(),
    "Yolol100/programmeren": set(),
    "Yolol100/wordpressconnector": {"elementor"},
    "Yolol100/transcriberen": set(),
    "Yolol100/Leadscanner": set(),
    "Yolol100/vacature-engine": set(),
}
EXPECTED_DISPATCHER_REGISTRATION = {
    "Yolol100/Orchestrator": False,
    "Yolol100/Designchecker": True,
    "Yolol100/seochecker": True,
    "Yolol100/elementorjson": True,
    "Yolol100/programmeren": True,
    "Yolol100/wordpressconnector": False,
    "Yolol100/transcriberen": True,
    "Yolol100/Leadscanner": True,
    "Yolol100/vacature-engine": False,
}
EXPECTED_EXCLUDED: set[str] = set()
FORBIDDEN_ACTIVE = {
    "Yolol100/Checklist",
    "Yolol100/Elementorconnector",
    "Yolol100/Export-acf-to-csv",
    "Yolol100/elementor-design-kit-generator",
    "Yolol100/Woocommerce-return-requests",
    "Yolol100/outreach-runtime",
}
ALLOWED_CONSOLIDATION_STATUS = {"migration", "duplicate-deprecation"}


def validate(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    if data.get("schema_version") != "1.1":
        errors.append("schema_version must be 1.1")
    if data.get("controller") != "webactueel-workflow":
        errors.append("controller must be webactueel-workflow")
    if not data.get("selection_rule") or not data.get("cross_skill_rule"):
        errors.append("selection_rule and cross_skill_rule are required")

    core = data.get("core_repositories")
    if not isinstance(core, list):
        return errors + ["core_repositories must be an array"]
    core_repos = [item.get("repository") for item in core if isinstance(item, dict)]
    if len(core_repos) != len(set(core_repos)):
        errors.append("core repositories must be unique")
    if set(core_repos) != EXPECTED_CORE:
        errors.append("core repository set differs from the nine-repository platform contract")
    if set(core_repos) & FORBIDDEN_ACTIVE:
        errors.append("consolidation/deprecated/archive/deleted repository is active core")

    for item in core:
        if not isinstance(item, dict):
            errors.append("core entry must be an object")
            continue
        repo = item.get("repository")
        for field in ("id", "repository", "owner_skill", "role", "status", "call_when", "do_not_call_when"):
            if not item.get(field):
                errors.append(f"core entry missing {field}: {item!r}")
        if item.get("status") != "active":
            errors.append(f"core repository is not active: {repo}")
        if repo in EXPECTED_OWNERS and item.get("owner_skill") != EXPECTED_OWNERS[repo]:
            errors.append(f"wrong owner_skill for {repo}: {item.get('owner_skill')}")

        consumers = item.get("consumer_skills")
        if not isinstance(consumers, list):
            errors.append(f"consumer_skills must be an array: {repo}")
            consumers = []
        if len(consumers) != len(set(consumers)):
            errors.append(f"consumer_skills must be unique: {repo}")
        if item.get("owner_skill") in consumers:
            errors.append(f"owner_skill may not repeat as consumer: {repo}")
        if repo in EXPECTED_CONSUMERS and set(consumers) != EXPECTED_CONSUMERS[repo]:
            errors.append(f"consumer_skills differ from explicit allowlist for {repo}")

        dispatcher = item.get("dispatcher_registration")
        if not isinstance(dispatcher, bool):
            errors.append(f"dispatcher_registration must be boolean: {repo}")
        elif repo in EXPECTED_DISPATCHER_REGISTRATION and dispatcher != EXPECTED_DISPATCHER_REGISTRATION[repo]:
            errors.append(f"dispatcher registration mismatch for {repo}")

    leadscanner = next((item for item in core if isinstance(item, dict) and item.get("repository") == "Yolol100/Leadscanner"), None)
    if not leadscanner or leadscanner.get("owner_skill") != "leads" or leadscanner.get("role") != "leads-domain-runtime":
        errors.append("Leadscanner must be leads-owned leads-domain-runtime")

    vacancy = next((item for item in core if isinstance(item, dict) and item.get("repository") == "Yolol100/vacature-engine"), None)
    if not vacancy or vacancy.get("owner_skill") != "vacature-search" or vacancy.get("dispatcher_registration") is not False:
        errors.append("vacature-engine must be vacancy-search-owned and must not become a dispatcher adapter")

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
        if item.get("new_feature_policy") != "blocked":
            errors.append(f"consolidation must block new features: {source}")

    excluded = data.get("excluded_repositories")
    if not isinstance(excluded, list):
        errors.append("excluded_repositories must be an array")
        excluded = []
    excluded_repos = {item.get("repository") for item in excluded if isinstance(item, dict)}
    if excluded_repos != EXPECTED_EXCLUDED:
        errors.append("excluded repository set must be empty")
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
    print("PLATFORM ARCHITECTURE: PASS (9 active repositories; single owners; explicit cross-skill consumers; vacancy-engine isolated under Vacature Search)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
