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


class PlatformArchitectureTests(unittest.TestCase):
    def test_current_contract_is_valid(self) -> None:
        self.assertEqual(MODULE.validate(BASE), [])

    def test_duplicate_core_repository_fails(self) -> None:
        data = copy.deepcopy(BASE)
        data["core_repositories"].append(copy.deepcopy(data["core_repositories"][0]))
        self.assertTrue(MODULE.validate(data))

    def test_excluded_repository_cannot_become_core(self) -> None:
        data = copy.deepcopy(BASE)
        data["core_repositories"][0]["repository"] = "Yolol100/Leadscanner"
        self.assertTrue(MODULE.validate(data))

    def test_consolidation_requires_exit_gates(self) -> None:
        data = copy.deepcopy(BASE)
        data["consolidations"][0]["remove_after"] = []
        self.assertTrue(MODULE.validate(data))


if __name__ == "__main__":
    unittest.main()
