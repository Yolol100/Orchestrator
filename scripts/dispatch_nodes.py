#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


class GitHubAPIError(RuntimeError):
    def __init__(self, endpoint: str, returncode: int, stderr: str):
        super().__init__(f'GitHub API failed ({returncode}) for {endpoint}: {stderr.strip()}')
        self.endpoint = endpoint
        self.returncode = returncode
        self.stderr = stderr

    @property
    def is_not_found(self) -> bool:
        text = self.stderr.lower()
        return 'http 404' in text or 'status 404' in text or 'not found' in text


def gh(method: str, endpoint: str, payload: dict | None = None) -> object:
    if not os.environ.get('GH_TOKEN'):
        raise RuntimeError('GH_TOKEN is required')
    cmd = ['gh', 'api', '--method', method, endpoint, '-H', 'Accept: application/vnd.github+json', '-H', 'X-GitHub-Api-Version: 2022-11-28']
    input_bytes = None
    if payload is not None:
        cmd += ['--input', '-']
        input_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    proc = subprocess.run(cmd, input=input_bytes, capture_output=True)
    if proc.returncode != 0:
        raise GitHubAPIError(endpoint, proc.returncode, proc.stderr.decode('utf-8', errors='replace'))
    if not proc.stdout:
        return {}
    return json.loads(proc.stdout.decode('utf-8'))


def get_ref_sha(repo: str, ref: str) -> str:
    data = gh('GET', f"repos/{repo}/git/ref/heads/{quote(ref, safe='')}")
    return str(data['object']['sha'])


def try_get_ref_sha(repo: str, ref: str) -> str | None:
    try:
        return get_ref_sha(repo, ref)
    except GitHubAPIError as exc:
        if exc.is_not_found:
            return None
        raise


def create_ref(repo: str, branch: str, base_sha: str) -> None:
    gh('POST', f'repos/{repo}/git/refs', {'ref': f'refs/heads/{branch}', 'sha': base_sha})


def get_file(repo: str, branch: str, path: str) -> dict | None:
    endpoint = f"repos/{repo}/contents/{quote(path, safe='/')}?ref={quote(branch, safe='')}"
    try:
        data = gh('GET', endpoint)
    except GitHubAPIError as exc:
        if exc.is_not_found:
            return None
        raise
    if not isinstance(data, dict) or data.get('type') not in (None, 'file'):
        raise RuntimeError(f'{repo}:{branch}:{path} did not resolve to a file')
    return data


def decode_file_json(data: dict) -> object:
    content = str(data.get('content') or '').replace('\n', '')
    if data.get('encoding') != 'base64' or not content:
        raise RuntimeError('existing request file is not base64 encoded content')
    raw = base64.b64decode(content).decode('utf-8')
    return json.loads(raw)


def latest_commit_for_path(repo: str, branch: str, path: str) -> str:
    endpoint = f"repos/{repo}/commits?sha={quote(branch, safe='')}&path={quote(path, safe='')}&per_page=1"
    data = gh('GET', endpoint)
    if not isinstance(data, list) or not data:
        raise RuntimeError(f'cannot locate commit provenance for {repo}:{branch}:{path}')
    return str(data[0]['sha'])


def put_file(repo: str, branch: str, path: str, payload: dict, message: str) -> str:
    encoded = base64.b64encode((json.dumps(payload, indent=2, ensure_ascii=False) + '\n').encode('utf-8')).decode('ascii')
    data = gh('PUT', f"repos/{repo}/contents/{quote(path, safe='/')}", {
        'message': message,
        'content': encoded,
        'branch': branch,
    })
    return str(data['commit']['sha'])


def same_payload(existing: dict, payload: dict) -> bool:
    try:
        return decode_file_json(existing) == payload
    except Exception:
        return False


def safe_branch_component(value: str) -> str:
    value = re.sub(r'[^a-z0-9._-]+', '-', value.lower()).strip('-')
    return value or 'node'


def ensure_ephemeral_request(repo: str, base_ref: str, branch: str, path: str, payload: dict, message: str) -> tuple[str, str]:
    base_sha = get_ref_sha(repo, base_ref)
    branch_sha = try_get_ref_sha(repo, branch)
    if branch_sha is None:
        create_ref(repo, branch, base_sha)
        branch_sha = base_sha
    existing = get_file(repo, branch, path)
    if existing is not None:
        if same_payload(existing, payload):
            return 'duplicate_ignored', latest_commit_for_path(repo, branch, path)
        raise RuntimeError(f'idempotency conflict: {repo}:{branch}:{path} already exists with different content')
    if branch_sha != base_sha:
        raise RuntimeError(f'idempotency conflict: existing branch {repo}:{branch} moved before request creation')
    return 'invoked', put_file(repo, branch, path, payload, message)


def ensure_append_request(repo: str, branch: str, path: str, payload: dict, message: str) -> tuple[str, str]:
    if try_get_ref_sha(repo, branch) is None:
        raise RuntimeError(f'fixed request branch does not exist: {repo}:{branch}')
    existing = get_file(repo, branch, path)
    if existing is not None:
        if same_payload(existing, payload):
            return 'duplicate_ignored', latest_commit_for_path(repo, branch, path)
        raise RuntimeError(f'idempotency conflict: {repo}:{branch}:{path} already exists with different content')
    try:
        return 'invoked', put_file(repo, branch, path, payload, message)
    except GitHubAPIError:
        existing = get_file(repo, branch, path)
        if existing is not None and same_payload(existing, payload):
            return 'duplicate_ignored', latest_commit_for_path(repo, branch, path)
        raise


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit('usage: dispatch_nodes.py REQUEST.json OUTPUT.json')
    request_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    request_bytes = request_path.read_bytes()
    request_sha256 = hashlib.sha256(request_bytes).hexdigest()
    request = json.loads(request_bytes.decode('utf-8'))
    nodes_by_id = {node['id']: node for node in request['nodes']}
    receipts = request.get('dependency_receipts') or {}
    accepted_dependencies = set(receipts)
    results: list[dict] = []
    temporary_branches: list[dict] = []

    for node_id in request['execution_order']:
        node = nodes_by_id[node_id]
        dependencies = list(node.get('dependencies') or [])
        missing = [dep for dep in dependencies if dep not in accepted_dependencies]
        if missing:
            results.append({
                'id': node_id,
                'status': 'waiting_dependencies',
                'dependencies': dependencies,
                'missing_dependencies': missing,
            })
            continue

        invocation = node['invocation']
        if invocation.get('mode') != 'request_file':
            raise RuntimeError(f'{node_id}: only request_file is supported by the current orchestrator blueprint')
        payload = invocation.get('payload')
        if not isinstance(payload, dict):
            raise RuntimeError(f'{node_id}: request_file requires a JSON object payload')
        path = str(invocation.get('path') or '')
        if not path or path.startswith('/') or '..' in Path(path).parts:
            raise RuntimeError(f'{node_id}: unsafe request path')

        repo = node['repository']
        branch_mode = invocation.get('branch_mode')
        message = f"runtime: {request['workflow_id']} g{request['generation']} {node_id}"
        event_id = f"{request['idempotency_key']}:{node_id}"

        if branch_mode == 'ephemeral_runtime_branch':
            branch = (
                f"runtime/{safe_branch_component(request['workflow_id'])}-"
                f"g{request['generation']}-{safe_branch_component(node_id)}-"
                f"{request['idempotency_key'][:8]}"
            )[:180]
            status, head_sha = ensure_ephemeral_request(
                repo,
                str(invocation.get('base_ref') or 'main'),
                branch,
                path,
                payload,
                message,
            )
            temporary_branches.append({'repository': repo, 'branch': branch, 'cleanup_required': True})
        elif branch_mode == 'append_existing_branch':
            branch = str(invocation.get('target_branch') or invocation.get('base_ref') or '')
            if not branch:
                raise RuntimeError(f'{node_id}: append_existing_branch requires target_branch')
            status, head_sha = ensure_append_request(repo, branch, path, payload, message)
        else:
            raise RuntimeError(f'{node_id}: unsupported branch_mode {branch_mode!r}')

        results.append({
            'id': node_id,
            'status': status,
            'mode': 'request_file',
            'repository': repo,
            'workflow': node['workflow'],
            'branch': branch,
            'head_sha': head_sha,
            'request_path': path,
            'event_id': event_id,
            'correlation': {
                'request_path': path,
                'head_sha': head_sha,
                'workflow': node['workflow'],
                'artifact_pattern': node.get('artifact_pattern'),
                'result': node.get('result'),
                'result_pattern': node.get('result_pattern'),
            },
        })

    invoked = [item for item in results if item['status'] in {'invoked', 'duplicate_ignored'}]
    waiting = [item for item in results if item['status'] == 'waiting_dependencies']
    runtime_state = 'waiting' if invoked or waiting else 'validating'
    output = {
        'schema_version': '1.0',
        'workflow_id': request['workflow_id'],
        'generation': request['generation'],
        'idempotency_key': request['idempotency_key'],
        'registry_fingerprint': request['registry_fingerprint'],
        'request_sha256': request_sha256,
        'runtime_state': runtime_state,
        'return_to': 'webactueel-workflow',
        'nodes': results,
        'temporary_branches': temporary_branches,
        'next_action': 'controller_readback_and_resume',
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
