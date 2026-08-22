#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('request', type=Path)
    parser.add_argument('transport', type=Path)
    args = parser.parse_args()
    request_bytes = args.request.read_bytes()
    request = json.loads(request_bytes.decode('utf-8'))
    transport = json.loads(args.transport.read_text(encoding='utf-8'))
    errors: list[str] = []

    for key in ('workflow_id', 'generation', 'idempotency_key', 'registry_fingerprint'):
        if transport.get(key) != request.get(key): errors.append(f'mismatch:{key}')
    if transport.get('request_sha256') != hashlib.sha256(request_bytes).hexdigest(): errors.append('request_sha256')
    if transport.get('return_to') != 'webactueel-workflow': errors.append('return_to')
    if transport.get('next_action') != 'controller_readback_and_resume': errors.append('next_action')

    request_nodes = {node['id']: node for node in request['nodes']}
    transport_nodes = transport.get('nodes') if isinstance(transport.get('nodes'), list) else []
    if {node.get('id') for node in transport_nodes} != set(request_nodes): errors.append('node_set')
    accepted = set((request.get('dependency_receipts') or {}).keys())
    for item in transport_nodes:
        node_id = item.get('id'); source = request_nodes.get(node_id)
        if not source: continue
        missing = [dep for dep in source.get('dependencies', []) if dep not in accepted]
        status = item.get('status')
        if missing:
            if status != 'waiting_dependencies' or sorted(item.get('missing_dependencies') or []) != sorted(missing): errors.append(f'dependency_gate:{node_id}')
            continue
        if status not in {'invoked', 'duplicate_ignored'}:
            errors.append(f'invocation_status:{node_id}'); continue
        if item.get('repository') != source.get('repository') or item.get('workflow') != source.get('workflow'): errors.append(f'node_identity:{node_id}')
        if item.get('executor_workflow') != source.get('executor_workflow'): errors.append(f'executor_workflow:{node_id}')
        invocation = source.get('invocation') or {}
        if item.get('mode') != invocation.get('mode'): errors.append(f'invocation_mode:{node_id}')
        if item.get('request_path') != invocation.get('path'): errors.append(f'request_path:{node_id}')
        if not re.fullmatch(r'[0-9a-f]{40}', str(item.get('head_sha') or '')): errors.append(f'head_sha:{node_id}')
        if item.get('event_id') != f"{request['idempotency_key']}:{node_id}": errors.append(f'event_id:{node_id}')
        if invocation.get('mode') == 'pull_request':
            pr = item.get('pull_request') if isinstance(item.get('pull_request'), dict) else {}
            if not isinstance(pr.get('number'), int) or pr.get('number', 0) < 1: errors.append(f'pull_request_number:{node_id}')
            if pr.get('request_head_sha') != item.get('head_sha'): errors.append(f'pull_request_head:{node_id}')

    temp = transport.get('temporary_branches') if isinstance(transport.get('temporary_branches'), list) else []
    for entry in temp:
        if entry.get('cleanup_required') is not True or not str(entry.get('branch') or '').startswith('runtime/'): errors.append('temporary_branch_contract')

    if errors:
        print('TRANSPORT PLAN: FAIL')
        for error in sorted(set(errors)): print('ERROR', error)
        return 1
    print('TRANSPORT PLAN: PASS')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
