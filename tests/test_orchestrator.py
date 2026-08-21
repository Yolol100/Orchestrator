from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def load_dispatch_module():
    path = ROOT / 'scripts' / 'dispatch_nodes.py'
    spec = importlib.util.spec_from_file_location('dispatch_nodes_under_test', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / 'config' / 'adapter-registry.json').read_text(encoding='utf-8'))
        self.adapters = {item['id']: item for item in self.registry['adapters']}
        self.registry_fp = hashlib.sha256(canonical(self.registry)).hexdigest()
        os.environ['GH_TOKEN_CONTENTS'] = 'test-token'
        os.environ['GH_TOKEN_PULL_REQUESTS'] = 'test-pr-token'

    def make_node(self, node_id: str, payload: dict, dependencies=None):
        adapter = self.adapters[node_id]
        dispatcher = adapter['dispatcher']
        path = adapter.get('request_file')
        if adapter.get('request_file_pattern'):
            path = adapter['request_file_pattern'].replace('<request_id>', payload['request_id'])
        mode = dispatcher.get('support') if dispatcher.get('support') in {'request_file', 'pull_request'} else 'request_file'
        return {'id': node_id,'repository': adapter['repository'],'owner_skill': adapter['owner_skill'],'project_id': adapter['project_id'],'workflow': adapter['workflow'],'request_file': adapter.get('request_file'),'request_file_pattern': adapter.get('request_file_pattern'),'result': adapter.get('result'),'result_pattern': adapter.get('result_pattern'),'artifact_pattern': adapter.get('artifact_pattern'),'remote_trigger': adapter.get('remote_trigger'),'dependencies': dependencies or [],'operation': dispatcher['default_operation'],'input_fingerprint': 'b' * 64,'dispatcher': dispatcher,'invocation': {'mode': mode,'path': path,'base_ref': dispatcher.get('base_ref'),'branch_mode': dispatcher.get('branch_mode'),'target_branch': dispatcher.get('target_branch'),'payload': payload}}

    def make_request(self, nodes, order, receipts=None):
        mutating = any(node.get('operation') in {'write', 'publish', 'release'} for node in nodes)
        approval = 'approval_before_write' if mutating else 'autonomous'
        return {'schema_version':'1.0','workflow_id':'WF-ABCDEF123456','id_seed_sha256':'a'*64,'work_item_id':'wi-test','generation':1,'idempotency_key':'c'*64,'registry_fingerprint':self.registry_fp,'transport_mode':'github_app','workflow_state':'execution_active','runtime_state':'queued','approval_policy':approval,'return_to':'webactueel-workflow','execution_order':order,'dependency_receipts':receipts or {},'nodes':nodes,'recovery':{'max_retries':2,'retry_only_transient':True,'fail_closed':True,'timeout_minutes':60,'rollback_required':mutating}}

    def test_validator_and_dependency_wave(self):
        seo = self.make_node('seochecker', {'request_id':'seo-123','url':'https://example.com'})
        qa = self.make_node('checklist', {'request_id':'qa-123','url':'https://example.com','level':'quick','task_type':'audit'}, ['seochecker'])
        request = self.make_request([seo, qa], ['seochecker', 'checklist'])
        with tempfile.TemporaryDirectory() as raw:
            td=Path(raw); request_path=td/'request.json'; request_path.write_text(json.dumps(request),encoding='utf-8')
            proc=subprocess.run(['python3',str(ROOT/'scripts'/'validate_request.py'),str(request_path)],capture_output=True,text=True); self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            module=load_dispatch_module(); calls=[]; module.ensure_ephemeral_request=lambda repo,base,branch,path,payload,message:(calls.append((repo,path)) or ('invoked','d'*40))
            old_argv=sys.argv
            try:
                sys.argv=['dispatch_nodes.py',str(request_path),str(td/'transport.json')]; self.assertEqual(module.main(),0)
            finally: sys.argv=old_argv
            transport=json.loads((td/'transport.json').read_text(encoding='utf-8')); statuses={item['id']:item['status'] for item in transport['nodes']}
            self.assertEqual(statuses['seochecker'],'invoked'); self.assertEqual(statuses['checklist'],'waiting_dependencies'); self.assertEqual(len(calls),1); self.assertEqual(calls[0][0],'Yolol100/seochecker')
            subprocess.run(['python3',str(ROOT/'scripts'/'validate_transport_plan.py'),str(request_path),str(td/'transport.json')],check=True,capture_output=True,text=True)

    def test_append_existing_branch_is_preserved(self):
        transcribe=self.make_node('transcriberen',{'request_id':'caption-123','url':'https://www.youtube.com/watch?v=abc'}); request=self.make_request([transcribe],['transcriberen'])
        with tempfile.TemporaryDirectory() as raw:
            td=Path(raw); request_path=td/'request.json'; request_path.write_text(json.dumps(request),encoding='utf-8'); module=load_dispatch_module(); seen={}
            def append(repo,branch,path,payload,message): seen.update(repo=repo,branch=branch,path=path); return 'invoked','e'*40
            module.ensure_append_request=append; old_argv=sys.argv
            try:
                sys.argv=['dispatch_nodes.py',str(request_path),str(td/'transport.json')]; self.assertEqual(module.main(),0)
            finally: sys.argv=old_argv
            self.assertEqual(seen['branch'],'runtime-requests'); self.assertEqual(seen['path'],'requests/queue/caption-123.json')

    def test_wordpressconnector_uses_guarded_pull_request_transport(self):
        wp=self.make_node('wordpressconnector',{'version':1,'request_id':'wpconn-123','action':'connector.discover','dry_run':True,'confirm':False,'payload':{}}); request=self.make_request([wp],['wordpressconnector'])
        with tempfile.TemporaryDirectory() as raw:
            td=Path(raw); request_path=td/'request.json'; request_path.write_text(json.dumps(request),encoding='utf-8'); output_env=td/'github-output.txt'
            proc=subprocess.run(['python3',str(ROOT/'scripts'/'validate_request.py'),str(request_path),'--github-output',str(output_env)],capture_output=True,text=True); self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            outputs=output_env.read_text(encoding='utf-8'); self.assertIn('has_pr_nodes=true',outputs); self.assertIn('wordpressconnector',outputs)
            module=load_dispatch_module(); seen={}
            def pr_request(repo,base,branch,path,payload,message,title,body): seen.update(repo=repo,base=base,branch=branch,path=path,title=title); return 'invoked','a'*40,42,'https://github.com/Yolol100/wordpressconnector/pull/42'
            module.ensure_pull_request_request=pr_request; old_argv=sys.argv
            try:
                sys.argv=['dispatch_nodes.py',str(request_path),str(td/'transport.json')]; self.assertEqual(module.main(),0)
            finally: sys.argv=old_argv
            transport=json.loads((td/'transport.json').read_text(encoding='utf-8')); item=transport['nodes'][0]
            self.assertEqual(item['mode'],'pull_request'); self.assertEqual(item['pull_request']['number'],42); self.assertEqual(item['head_sha'],'a'*40); self.assertTrue(seen['branch'].startswith('runtime/')); self.assertEqual(seen['path'],'requests/wpconn-123.json')
            subprocess.run(['python3',str(ROOT/'scripts'/'validate_transport_plan.py'),str(request_path),str(td/'transport.json')],check=True,capture_output=True,text=True)

    def test_exact_duplicate_is_ignored(self):
        module=load_dispatch_module(); payload={'request_id':'seo-123','url':'https://example.com'}; encoded=base64.b64encode((json.dumps(payload)+'\n').encode()).decode()
        module.get_ref_sha=lambda repo,ref:'a'*40; module.try_get_ref_sha=lambda repo,ref:'a'*40; module.get_file=lambda repo,branch,path:{'type':'file','encoding':'base64','content':encoded}; module.latest_commit_for_path=lambda repo,branch,path:'f'*40; module.create_ref=lambda *args:self.fail('create_ref should not run for duplicate'); module.put_file=lambda *args:self.fail('put_file should not run for duplicate')
        status,sha=module.ensure_ephemeral_request('Yolol100/seochecker','main','runtime/test','requests/audit.json',payload,'msg'); self.assertEqual(status,'duplicate_ignored'); self.assertEqual(sha,'f'*40)

    def test_handoff_adapter_is_rejected(self):
        adapter=self.adapters['elementorjson']; node={'id':'elementorjson','repository':adapter['repository'],'owner_skill':adapter['owner_skill'],'project_id':adapter['project_id'],'workflow':adapter['workflow'],'request_file':adapter.get('request_file'),'request_file_pattern':adapter.get('request_file_pattern'),'result':adapter.get('result'),'result_pattern':adapter.get('result_pattern'),'artifact_pattern':adapter.get('artifact_pattern'),'remote_trigger':adapter.get('remote_trigger'),'dependencies':[],'operation':'test','input_fingerprint':'b'*64,'dispatcher':adapter['dispatcher'],'invocation':{'mode':'request_file','path':None,'base_ref':'main','branch_mode':'ephemeral_runtime_branch','target_branch':None,'payload':{}}}
        request=self.make_request([node],['elementorjson'])
        with tempfile.TemporaryDirectory() as raw:
            p=Path(raw)/'request.json'; p.write_text(json.dumps(request),encoding='utf-8'); proc=subprocess.run(['python3',str(ROOT/'scripts'/'validate_request.py'),str(p)],capture_output=True,text=True); self.assertNotEqual(proc.returncode,0); self.assertIn('unsupported_dispatcher:elementorjson',proc.stdout)


if __name__ == '__main__':
    unittest.main()
