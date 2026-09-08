from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("platform_validator", ROOT / "scripts/validate_platform_architecture.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)
BASE = json.loads((ROOT / "config/platform-repositories.json").read_text(encoding="utf-8"))
ADAPTERS = json.loads((ROOT / "config/adapter-registry.json").read_text(encoding="utf-8"))


class PlatformArchitectureTests(unittest.TestCase):
    def test_current_contract_is_valid(self) -> None:
        self.assertEqual(MODULE.validate(BASE), [])

    def test_duplicate_core_repository_fails(self) -> None:
        data = copy.deepcopy(BASE)
        data["core_repositories"].append(copy.deepcopy(data["core_repositories"][0]))
        self.assertTrue(MODULE.validate(data))

    def test_core_repository_cannot_also_be_excluded(self) -> None:
        data = copy.deepcopy(BASE)
        data["excluded_repositories"].append({"repository": "Yolol100/vacature-engine", "reason": "bad overlap"})
        self.assertTrue(MODULE.validate(data))

    def test_owner_cannot_repeat_as_consumer(self) -> None:
        data = copy.deepcopy(BASE)
        designchecker = next(item for item in data["core_repositories"] if item["repository"] == "Yolol100/Designchecker")
        designchecker["consumer_skills"].append("design")
        self.assertTrue(MODULE.validate(data))

    def test_cross_skill_consumer_is_deny_by_default(self) -> None:
        data = copy.deepcopy(BASE)
        seochecker = next(item for item in data["core_repositories"] if item["repository"] == "Yolol100/seochecker")
        seochecker["consumer_skills"].append("website-qa-checklist")
        self.assertTrue(MODULE.validate(data))

    def test_vacature_engine_is_isolated_under_vacature_search(self) -> None:
        vacancy = next(item for item in BASE["core_repositories"] if item["repository"] == "Yolol100/vacature-engine")
        self.assertEqual(vacancy["owner_skill"], "vacature-search")
        self.assertEqual(vacancy["consumer_skills"], [])
        self.assertFalse(vacancy["dispatcher_registration"])

    def test_wordpressconnector_cross_skill_use_is_elementor_only(self) -> None:
        connector = next(item for item in BASE["core_repositories"] if item["repository"] == "Yolol100/wordpressconnector")
        self.assertEqual(connector["owner_skill"], "wordpressqualityarchitect")
        self.assertEqual(connector["consumer_skills"], ["elementor"])

    def test_dispatcher_registry_matches_platform_registration(self) -> None:
        registered = {item["repository"] for item in ADAPTERS["adapters"]}
        expected_active = {
            item["repository"]
            for item in BASE["core_repositories"]
            if item["dispatcher_registration"] is True
        }
        self.assertEqual(registered, expected_active | {"Yolol100/Checklist"})

    def test_consolidation_requires_exit_gates(self) -> None:
        data = copy.deepcopy(BASE)
        data["consolidations"][0]["remove_after"] = []
        self.assertTrue(MODULE.validate(data))

    def test_consolidation_blocks_new_features(self) -> None:
        data = copy.deepcopy(BASE)
        data["consolidations"][0]["new_feature_policy"] = "allowed"
        self.assertTrue(MODULE.validate(data))


if __name__ == "__main__":
    unittest.main()
