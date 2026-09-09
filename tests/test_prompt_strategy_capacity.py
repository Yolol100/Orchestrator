from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_validator():
    path = ROOT / 'scripts' / 'validate_request.py'
    spec = importlib.util.spec_from_file_location('validate_request_under_test', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class PromptStrategyCapacityTests(unittest.TestCase):
    def setUp(self):
        self.module = load_validator()
        self.registry = json.loads((ROOT / 'config' / 'prompt-technique-registry.json').read_text(encoding='utf-8'))

    def receipt(self, techniques):
        return {
            'contract_sha256': self.registry['prompt_strategy_contract_sha256'],
            'strategy_sha256': 'a' * 64,
            'techniques': list(techniques),
            'research_status': 'complete',
            'verification': ['verify outcome'],
        }

    def test_all_registered_techniques_fit_transport_contract(self):
        techniques = self.registry['techniques']
        self.assertEqual(len(techniques), 20)
        self.assertEqual(self.module.validate_prompt_strategy(self.receipt(techniques), self.registry), [])

    def test_unknown_or_over_capacity_receipt_fails_closed(self):
        techniques = self.registry['techniques'] + ['unknown-technique']
        errors = self.module.validate_prompt_strategy(self.receipt(techniques), self.registry)
        self.assertIn('prompt_strategy_techniques', errors)


if __name__ == '__main__':
    unittest.main()
