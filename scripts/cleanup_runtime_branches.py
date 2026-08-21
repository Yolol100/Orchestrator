#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import quote


def gh(method: str, endpoint: str) -> object:
    if not os.environ.get('GH_TOKEN'):
        raise RuntimeError('GH_TOKEN is required')
    proc = subprocess.run(
        ['gh', 'api', '--method', method, endpoint, '-H', 'Accept: application/vnd.github+json', '-H', 'X-GitHub-Api-Version: 2022-11-28'],
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
    args = parser.parse_args()
    plan = json.loads(args.transport_plan.read_text(encoding='utf-8'))
    if plan.get('workflow_id') != args.confirm_workflow_id:
        raise SystemExit('workflow confirmation mismatch')
    node_heads = {(node.get('repository'), node.get('branch')): node.get('head_sha') for node in plan.get('nodes', []) if node.get('head_sha')}
    deleted = []
    for entry in plan.get('temporary_branches', []):
        if entry.get('cleanup_required') is not True:
            continue
        repo = str(entry.get('repository') or '')
        branch = str(entry.get('branch') or '')
        if not branch.startswith('runtime/'):
            raise SystemExit(f'refuse non-runtime branch cleanup: {repo}:{branch}')
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
