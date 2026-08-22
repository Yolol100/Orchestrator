#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import re
from pathlib import Path
from urllib.parse import quote


def gh(method: str, endpoint: str) -> object:
    if not os.environ.get('GH_TOKEN'):
        raise RuntimeError('GH_TOKEN is required')
    proc = subprocess.run(
        ['gh', 'api', '--method', method, endpoint, '-H', 'Accept: application/vnd.github+json', '-H', 'X-GitHub-Api-Version: 2026-03-10'],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode('utf-8', errors='replace').strip())
    if not proc.stdout:
        return {}
    return json.loads(proc.stdout.decode('utf-8'))


def ref_sha(repo: str, branch: str) -> str:
    data = gh('GET', f"repos/{repo}/git/ref/heads/{quote(branch, safe='')}")
    return str(data['object']['sha'])


def main() -> int:
    parser = argparse.ArgumentParser(description='Delete only verified ephemeral runtime branches after controller closure/readback.')
    parser.add_argument('transport_plan', type=Path)
    parser.add_argument('--confirm-workflow-id', required=True)
    parser.add_argument('--verified-heads', type=Path, help='Controller-verified JSON mapping repository:branch to current 40-hex head SHA for branches that moved during result writeback.')
    args = parser.parse_args()
    plan = json.loads(args.transport_plan.read_text(encoding='utf-8'))
    if plan.get('workflow_id') != args.confirm_workflow_id:
        raise SystemExit('workflow confirmation mismatch')
    node_heads = {(node.get('repository'), node.get('branch')): node.get('head_sha') for node in plan.get('nodes', []) if node.get('head_sha')}
    verified_heads = {}
    if args.verified_heads:
        raw_verified = json.loads(args.verified_heads.read_text(encoding='utf-8'))
        if not isinstance(raw_verified, dict):
            raise SystemExit('verified heads must be a JSON object mapping repository:branch to head SHA')
        verified_heads = {str(key): str(value) for key, value in raw_verified.items()}
    deleted = []
    for entry in plan.get('temporary_branches', []):
        if entry.get('cleanup_required') is not True:
            continue
        repo = str(entry.get('repository') or '')
        branch = str(entry.get('branch') or '')
        if not branch.startswith('runtime/'):
            raise SystemExit(f'refuse non-runtime branch cleanup: {repo}:{branch}')
        if entry.get('cleanup_requires_controller_verified_head') is True:
            expected = verified_heads.get(f'{repo}:{branch}')
            if not expected or not re.fullmatch(r'[0-9a-f]{40}', expected):
                raise SystemExit(f'missing controller-verified current head for cleanup: {repo}:{branch}')
        else:
            expected = node_heads.get((repo, branch))
            if not expected:
                raise SystemExit(f'missing transport head for cleanup: {repo}:{branch}')
        actual = ref_sha(repo, branch)
        if actual != expected:
            raise SystemExit(f'refuse moved branch cleanup: {repo}:{branch} expected={expected} actual={actual}')
        gh('DELETE', f"repos/{repo}/git/refs/heads/{quote(branch, safe='')}")
        deleted.append({'repository': repo, 'branch': branch, 'head_sha': actual})
    print(json.dumps({'workflow_id': plan.get('workflow_id'), 'deleted': deleted}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
