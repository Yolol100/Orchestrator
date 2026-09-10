from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PhaseCorrelationContractTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((ROOT / 'schemas' / 'github-dispatch-request.schema.json').read_text(encoding='utf-8'))
        self.properties = self.schema['properties']

    def test_transport_keeps_controller_correlation_fields(self):
        self.assertIn('workflow_id', self.properties)
        self.assertIn('work_item_id', self.properties)
        self.assertIn('generation', self.properties)
        self.assertIn('idempotency_key', self.properties)
        self.assertIn('prompt_strategy', self.properties)
        self.assertIn('dependency_receipts', self.properties)
        receipt = self.properties['dependency_receipts']['additionalProperties']
        self.assertIn('checkpoint_id', receipt['required'])
        self.assertIn('evidence_ids', receipt['required'])

    def test_transport_does_not_become_phase_acceptance_controller(self):
        forbidden_top_level = {
            'execution_control',
            'phase_id',
            'phase_goal',
            'phase_acceptance',
            'phase_gate_decision',
            'audit_plan',
            'test_plan',
            'repair_loop',
            'global_complete',
        }
        self.assertFalse(forbidden_top_level & set(self.properties))
        self.assertEqual(self.properties['return_to'].get('const'), 'webactueel-workflow')

    def test_checkpoint_receipt_requires_controller_acceptance(self):
        receipt = self.properties['dependency_receipts']['additionalProperties']
        self.assertEqual(receipt['properties']['status'].get('const'), 'accepted')
        self.assertIn('accepted_by', receipt['required'])
        self.assertIn('generation', receipt['required'])
        self.assertIn('checkpoint_id', receipt['required'])
        self.assertIn('evidence_ids', receipt['required'])


if __name__ == '__main__':
    unittest.main()
