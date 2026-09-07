import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from classify_run_evidence import classify


class RunEvidenceTests(unittest.TestCase):
    def fixture(self):
        sha = 'a' * 40
        return {'expected': {'head_sha': sha, 'workflow_path': '.github/workflows/ci.yml', 'job_names': ['validate']}, 'run': {'id': 12, 'run_attempt': 2, 'head_sha': sha, 'path': '.github/workflows/ci.yml', 'status': 'completed', 'conclusion': 'success'}, 'jobs': {'total_count': 1, 'jobs': [{'name': 'validate', 'run_id': 12, 'run_attempt': 2, 'head_sha': sha, 'runner_id': 8, 'status': 'completed', 'conclusion': 'success', 'steps': [{'conclusion': 'success'}]}]}}

    def test_success_does_not_accept_domain_work(self):
        output = classify(self.fixture())
        self.assertEqual(output['status'], 'execution_verified')
        self.assertIs(output['domain_accepted'], False)

    def test_empty_or_partial_listing_cannot_pass(self):
        for listing in [{'total_count': 0, 'jobs': []}, {'total_count': 2, 'jobs': []}]:
            data = self.fixture(); data['jobs'] = listing
            self.assertNotEqual(classify(data)['status'], 'execution_verified')

    def test_runner_failure_is_not_a_code_test_result(self):
        data = self.fixture(); job = data['jobs']['jobs'][0]
        job.update(runner_id=0, steps=[], conclusion='failure')
        data['run']['conclusion'] = 'failure'
        self.assertEqual(classify(data)['status'], 'blocked')

    def test_old_head_attempt_skipped_and_failed_jobs_cannot_pass(self):
        for key, value in [('head_sha', 'b'*40), ('run_attempt', 1), ('run_id', 9), ('conclusion', 'skipped'), ('conclusion', 'failure')]:
            data = self.fixture(); data['jobs']['jobs'][0][key] = value
            self.assertNotEqual(classify(data)['status'], 'execution_verified')

    def test_missing_and_expired_artifacts_cannot_pass(self):
        data = self.fixture(); data['expected']['artifact_names'] = ['evidence']
        self.assertEqual(classify(data)['status'], 'incomplete')
        data['run']['run_started_at'] = '2026-09-07T12:00:00Z'
        item = {'name': 'evidence', 'expired': False, 'created_at': '2026-09-07T12:01:00Z', 'workflow_run': {'id': 12, 'head_sha': 'a'*40}}
        data['artifacts'] = {'total_count': 1, 'artifacts': [item]}
        self.assertEqual(classify(data)['status'], 'execution_verified')
        item['expired'] = True
        self.assertEqual(classify(data)['status'], 'incomplete')

    def test_missing_expectations_cannot_pass(self):
        for data in [None, {}, {'expected': {}, 'run': {}, 'jobs': {}}]:
            self.assertEqual(classify(data)['status'], 'invalid')

    def test_missing_attempt_and_malformed_run_are_rejected(self):
        data = self.fixture(); del data['run']['run_attempt']; del data['jobs']['jobs'][0]['run_attempt']
        self.assertEqual(classify(data)['status'], 'invalid')
        data = self.fixture(); data['run']['path'] = None
        self.assertEqual(classify(data)['status'], 'invalid')

    def test_ignored_step_failure_is_not_verified(self):
        data = self.fixture(); data['jobs']['jobs'][0]['steps'].append({'conclusion': 'failure'})
        self.assertEqual(classify(data)['status'], 'failed')

    def test_rerun_cannot_reuse_old_artifact(self):
        data = self.fixture(); data['expected']['artifact_names'] = ['evidence']
        data['run']['run_started_at'] = '2026-09-07T12:00:00Z'
        item = {'name': 'evidence', 'expired': False, 'created_at': '2026-09-07T11:00:00Z', 'workflow_run': {'id': 12, 'head_sha': 'a'*40}}
        data['artifacts'] = {'total_count': 1, 'artifacts': [item]}
        self.assertEqual(classify(data)['status'], 'stale')
        item['workflow_run'] = None
        self.assertEqual(classify(data)['status'], 'incomplete')
