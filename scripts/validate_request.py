#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / 'config' / 'adapter-registry.json'


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def sha(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def append_output(path: str | None, key: str, value: str) -> None:
    if not path:
        return
    with open(path, 'a', encoding='utf-8') as handle:
        if '\n' in value:
            marker = 'WEB_ACTUEEL_EOF'
            handle.write(f'{key}<<{marker}\n{value}\n{marker}\n')
        else:
            handle.write(f'{key}={value}\n')


def validate_graph(nodes: list[dict], execution_order: list[str], receipts: dict) -> list[str]:
    errors: list[str] = []
    ids = [str(node.get('id') or '') for node in nodes]
    if len(ids) != len(set(ids)):
        errors.append('duplicate_node_id')
    if set(execution_order) != set(ids) or len(execution_order) != len(ids):
        errors.append('execution_order')
    graph = {node['id']: list(node.get('dependencies') or []) for node in nodes if node.get('id')}
    accepted = set(receipts)
    for node_id, deps in graph.items():
        if node_id in deps:
            errors.append(f'self_dependency:{node_id}')
        for dep in deps:
            if dep not in graph and dep not in accepted:
                errors.append(f'unknown_dependency:{node_id}:{dep}')
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited or node_id not in graph:
            return
        if node_id in visiting:
            errors.append('dependency_cycle')
            return
        visiting.add(node_id)
        for dep in graph[node_id]:
            if dep in graph:
                visit(dep)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in execution_order:
        visit(node_id)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('request', type=Path)
    parser.add_argument('--github-output', default=os.environ.get('GITHUB_OUTPUT'))
    args = parser.parse_args()
    data = json.loads(args.request.read_text(encoding='utf-8'))
    registry = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
    known = {item['id']: item for item in registry.get('adapters', [])}
    errors: list[str] = []

    if data.get('schema_version') != '1.0': errors.append('schema_version')
    if not re.fullmatch(r'WF-[A-F0-9]{12}', str(data.get('workflow_id', ''))): errors.append('workflow_id')
    if not re.fullmatch(r'[a-f0-9]{64}', str(data.get('id_seed_sha256', ''))): errors.append('id_seed_sha256')
    if not re.fullmatch(r'[a-f0-9]{64}', str(data.get('idempotency_key', ''))): errors.append('idempotency_key')
    if data.get('registry_fingerprint') != sha(registry): errors.append('registry_fingerprint')
    if data.get('return_to') != 'webactueel-workflow': errors.append('return_to')
    if data.get('transport_mode') != 'github_app': errors.append('transport_mode_not_executable_here')
    if data.get('approval_policy') not in {'autonomous','approval_before_write','approval_before_publish','human_only'}: errors.append('approval_policy')

    receipts = data.get('dependency_receipts') if isinstance(data.get('dependency_receipts'), dict) else {}
    if not isinstance(data.get('dependency_receipts'), dict): errors.append('dependency_receipts')
    for node_id, receipt in receipts.items():
        if not isinstance(receipt, dict) or receipt.get('status') != 'accepted' or not receipt.get('evidence_ids') or not receipt.get('checkpoint_id') or not receipt.get('accepted_by'):
            errors.append(f'invalid_dependency_receipt:{node_id}')

    nodes = data.get('nodes') if isinstance(data.get('nodes'), list) else []
    if not nodes: errors.append('nodes')
    repositories: list[str] = []
    operations: set[str] = set()
    for node in nodes:
        node_id = node.get('id')
        adapter = known.get(node_id)
        if not adapter:
            errors.append(f'unknown_repo:{node_id}')
            continue
        for key in ('repository','owner_skill','project_id','workflow','request_file','request_file_pattern','result','result_pattern','artifact_pattern','remote_trigger'):
            if node.get(key) != adapter.get(key): errors.append(f'registry_mismatch:{node_id}:{key}')
        if node.get('dispatcher') != adapter.get('dispatcher'):
            errors.append(f'registry_mismatch:{node_id}:dispatcher')
            continue
        dispatcher = adapter.get('dispatcher') or {}
        if dispatcher.get('support') != 'request_file':
            errors.append(f'unsupported_dispatcher:{node_id}')
            continue
        invocation = node.get('invocation') or {}
        if invocation.get('mode') != 'request_file': errors.append(f'invocation_mode:{node_id}')
        expected_path = adapter.get('request_file')
        if adapter.get('request_file_pattern'):
            payload = invocation.get('payload') or {}
            request_id = str(payload.get('request_id') or '')
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{2,79}', request_id):
                errors.append(f'invalid_request_id:{node_id}')
            else:
                expected_path = adapter['request_file_pattern'].replace('<request_id>', request_id)
        if invocation.get('path') != expected_path: errors.append(f'request_path:{node_id}')
        if invocation.get('branch_mode') != dispatcher.get('branch_mode'): errors.append(f'branch_mode:{node_id}')
        if invocation.get('base_ref') != dispatcher.get('base_ref'): errors.append(f'base_ref:{node_id}')
        if invocation.get('target_branch') != dispatcher.get('target_branch'): errors.append(f'target_branch:{node_id}')
        if not isinstance(invocation.get('payload'), dict): errors.append(f'payload:{node_id}')
        if node.get('operation') != dispatcher.get('default_operation'): errors.append(f'operation:{node_id}')
        if not re.fullmatch(r'[a-f0-9]{64}', str(node.get('input_fingerprint', ''))): errors.append(f'input_fingerprint:{node_id}')
        operations.add(node.get('operation'))
        repositories.append(adapter['repository'].split('/', 1)[1])

    execution_order = data.get('execution_order') if isinstance(data.get('execution_order'), list) else []
    errors.extend(validate_graph(nodes, execution_order, receipts))
    if operations & {'write','publish','release'} and data.get('approval_policy') == 'autonomous': errors.append('approval_downgrade')
    if operations & {'publish','release'} and data.get('approval_policy') not in {'approval_before_publish','human_only'}: errors.append('publish_approval_policy')
    recovery = data.get('recovery') or {}
    mutating = bool(operations & {'write','publish','release'})
    if recovery.get('retry_only_transient') is not True or recovery.get('fail_closed') is not True: errors.append('recovery_policy')
    if not isinstance(recovery.get('max_retries'), int) or not 0 <= recovery.get('max_retries', -1) <= 3: errors.append('max_retries')
    if not isinstance(recovery.get('timeout_minutes'), int) or not 1 <= recovery.get('timeout_minutes', 0) <= 180: errors.append('timeout_minutes')
    if recovery.get('rollback_required') is not mutating: errors.append('rollback_required')

    if errors:
        print('GITHUB DISPATCH REQUEST: FAIL')
        for error in sorted(set(errors)):
            print('ERROR', error)
        return 1

    unique_repositories = []
    for repo in repositories:
        if repo not in unique_repositories:
            unique_repositories.append(repo)
    append_output(args.github_output, 'repositories', '\n'.join(unique_repositories))
    append_output(args.github_output, 'node_count', str(len(nodes)))
    append_output(args.github_output, 'workflow_id', str(data['workflow_id']))
    append_output(args.github_output, 'generation', str(data['generation']))
    print('GITHUB DISPATCH REQUEST: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
