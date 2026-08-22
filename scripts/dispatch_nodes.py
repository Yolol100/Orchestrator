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

_ACTIVE_TOKEN: str | None = None

class GitHubAPIError(RuntimeError):
    def __init__(self, endpoint: str, returncode: int, stderr: str):
        super().__init__(f'GitHub API failed ({returncode}) for {endpoint}: {stderr.strip()}')
        self.endpoint = endpoint; self.returncode = returncode; self.stderr = stderr
    @property
    def is_not_found(self) -> bool:
        text = self.stderr.lower()
        return 'http 404' in text or 'status 404' in text or 'not found' in text

def gh(method: str, endpoint: str, payload: dict | None = None) -> object:
    token = _ACTIVE_TOKEN or os.environ.get('GH_TOKEN')
    if not token: raise RuntimeError('GitHub token is required for the selected transport mode')
    cmd = ['gh','api','--method',method,endpoint,'-H','Accept: application/vnd.github+json','-H','X-GitHub-Api-Version: 2022-11-28']
    input_bytes = None
    if payload is not None:
        cmd += ['--input','-']; input_bytes = json.dumps(payload,separators=(',',':')).encode('utf-8')
    env=dict(os.environ); env['GH_TOKEN']=token
    proc=subprocess.run(cmd,input=input_bytes,capture_output=True,env=env)
    if proc.returncode != 0: raise GitHubAPIError(endpoint,proc.returncode,proc.stderr.decode('utf-8',errors='replace'))
    if not proc.stdout: return {}
    return json.loads(proc.stdout.decode('utf-8'))

def get_ref_sha(repo: str, ref: str) -> str:
    return str(gh('GET',f"repos/{repo}/git/ref/heads/{quote(ref,safe='')}")['object']['sha'])
def try_get_ref_sha(repo: str, ref: str) -> str | None:
    try: return get_ref_sha(repo,ref)
    except GitHubAPIError as exc:
        if exc.is_not_found: return None
        raise
def create_ref(repo: str, branch: str, base_sha: str) -> None: gh('POST',f'repos/{repo}/git/refs',{'ref':f'refs/heads/{branch}','sha':base_sha})
def get_file(repo: str, branch: str, path: str) -> dict | None:
    endpoint=f"repos/{repo}/contents/{quote(path,safe='/')}?ref={quote(branch,safe='')}"
    try: data=gh('GET',endpoint)
    except GitHubAPIError as exc:
        if exc.is_not_found: return None
        raise
    if not isinstance(data,dict) or data.get('type') not in (None,'file'): raise RuntimeError(f'{repo}:{branch}:{path} did not resolve to a file')
    return data
def decode_file_json(data: dict) -> object:
    content=str(data.get('content') or '').replace('\n','')
    if data.get('encoding')!='base64' or not content: raise RuntimeError('existing request file is not base64 encoded content')
    return json.loads(base64.b64decode(content).decode('utf-8'))
def latest_commit_for_path(repo: str, branch: str, path: str) -> str:
    data=gh('GET',f"repos/{repo}/commits?sha={quote(branch,safe='')}&path={quote(path,safe='')}&per_page=1")
    if not isinstance(data,list) or not data: raise RuntimeError(f'cannot locate commit provenance for {repo}:{branch}:{path}')
    return str(data[0]['sha'])
def put_file(repo: str, branch: str, path: str, payload: dict, message: str) -> str:
    encoded=base64.b64encode((json.dumps(payload,indent=2,ensure_ascii=False)+'\n').encode()).decode('ascii')
    data=gh('PUT',f"repos/{repo}/contents/{quote(path,safe='/')}",{'message':message,'content':encoded,'branch':branch})
    return str(data['commit']['sha'])
def same_payload(existing: dict,payload: dict)->bool:
    try: return decode_file_json(existing)==payload
    except Exception: return False
def safe_branch_component(value:str)->str:
    value=re.sub(r'[^a-z0-9._-]+','-',value.lower()).strip('-'); return value or 'node'
def deterministic_branch(request:dict,node_id:str)->str:
    return (f"runtime/{safe_branch_component(request['workflow_id'])}-g{request['generation']}-{safe_branch_component(node_id)}-{request['idempotency_key'][:8]}")[:180]
def ensure_ephemeral_request(repo,base_ref,branch,path,payload,message):
    base_sha=get_ref_sha(repo,base_ref); branch_sha=try_get_ref_sha(repo,branch)
    if branch_sha is None: create_ref(repo,branch,base_sha); branch_sha=base_sha
    existing=get_file(repo,branch,path)
    if existing is not None:
        if same_payload(existing,payload): return 'duplicate_ignored',latest_commit_for_path(repo,branch,path)
        raise RuntimeError(f'idempotency conflict: {repo}:{branch}:{path} already exists with different content')
    if branch_sha!=base_sha: raise RuntimeError(f'idempotency conflict: existing branch {repo}:{branch} moved before request creation')
    return 'invoked',put_file(repo,branch,path,payload,message)
def ensure_append_request(repo,branch,path,payload,message):
    if try_get_ref_sha(repo,branch) is None: raise RuntimeError(f'fixed request branch does not exist: {repo}:{branch}')
    existing=get_file(repo,branch,path)
    if existing is not None:
        if same_payload(existing,payload): return 'duplicate_ignored',latest_commit_for_path(repo,branch,path)
        raise RuntimeError(f'idempotency conflict: {repo}:{branch}:{path} already exists with different content')
    try: return 'invoked',put_file(repo,branch,path,payload,message)
    except GitHubAPIError:
        existing=get_file(repo,branch,path)
        if existing is not None and same_payload(existing,payload): return 'duplicate_ignored',latest_commit_for_path(repo,branch,path)
        raise
def find_open_pull_request(repo,branch,base_ref):
    owner=repo.split('/',1)[0]; head=quote(f'{owner}:{branch}',safe=''); base=quote(base_ref,safe='')
    data=gh('GET',f'repos/{repo}/pulls?state=open&head={head}&base={base}&per_page=10')
    if not isinstance(data,list): raise RuntimeError(f'unexpected pull request listing response for {repo}:{branch}')
    if len(data)>1: raise RuntimeError(f'multiple open pull requests for {repo}:{branch}')
    return data[0] if data else None
def ensure_pull_request_request(repo,base_ref,branch,path,payload,message,title,body):
    base_sha=get_ref_sha(repo,base_ref); branch_sha=try_get_ref_sha(repo,branch)
    if branch_sha is None: create_ref(repo,branch,base_sha); branch_sha=base_sha
    existing=get_file(repo,branch,path)
    if existing is not None:
        if not same_payload(existing,payload): raise RuntimeError(f'idempotency conflict: {repo}:{branch}:{path} already exists with different content')
        request_head_sha=latest_commit_for_path(repo,branch,path)
    else:
        if branch_sha!=base_sha: raise RuntimeError(f'idempotency conflict: existing branch {repo}:{branch} moved before request creation')
        request_head_sha=put_file(repo,branch,path,payload,message)
    pr=find_open_pull_request(repo,branch,base_ref)
    if pr is None:
        pr=gh('POST',f'repos/{repo}/pulls',{'title':title,'head':branch,'base':base_ref,'body':body,'maintainer_can_modify':False}); status='invoked'
    else: status='duplicate_ignored'
    return status,request_head_sha,int(pr['number']),str(pr.get('html_url') or pr.get('url') or '')

def main()->int:
    global _ACTIVE_TOKEN
    if len(sys.argv)!=3: raise SystemExit('usage: dispatch_nodes.py REQUEST.json OUTPUT.json')
    request_path=Path(sys.argv[1]); output_path=Path(sys.argv[2]); request_bytes=request_path.read_bytes(); request_sha256=hashlib.sha256(request_bytes).hexdigest(); request=json.loads(request_bytes.decode())
    nodes_by_id={node['id']:node for node in request['nodes']}; receipts=request.get('dependency_receipts') or {}; accepted_dependencies=set(receipts); results=[]; temporary_branches=[]
    for node_id in request['execution_order']:
        node=nodes_by_id[node_id]; dependencies=list(node.get('dependencies') or []); missing=[d for d in dependencies if d not in accepted_dependencies]
        if missing:
            results.append({'id':node_id,'status':'waiting_dependencies','dependencies':dependencies,'missing_dependencies':missing}); continue
        invocation=node['invocation']; mode=invocation.get('mode')
        if mode not in {'request_file','pull_request'}: raise RuntimeError(f'{node_id}: unsupported invocation mode {mode!r}')
        _ACTIVE_TOKEN=(os.environ.get('GH_TOKEN_PULL_REQUESTS') if mode=='pull_request' else os.environ.get('GH_TOKEN_CONTENTS')) or os.environ.get('GH_TOKEN')
        if not _ACTIVE_TOKEN: raise RuntimeError(f'{node_id}: missing GitHub token for {mode} transport')
        payload=invocation.get('payload'); path=str(invocation.get('path') or '')
        if not isinstance(payload,dict): raise RuntimeError(f'{node_id}: {mode} requires a JSON object payload')
        if not path or path.startswith('/') or '..' in Path(path).parts: raise RuntimeError(f'{node_id}: unsafe request path')
        repo=node['repository']; branch_mode=invocation.get('branch_mode'); message=f"runtime: {request['workflow_id']} g{request['generation']} {node_id}"; event_id=f"{request['idempotency_key']}:{node_id}"; branch=''; pr_number=None; pr_url=None
        if branch_mode=='ephemeral_runtime_branch' and mode=='request_file':
            branch=deterministic_branch(request,node_id); status,head_sha=ensure_ephemeral_request(repo,str(invocation.get('base_ref') or 'main'),branch,path,payload,message); temporary_branches.append({'repository':repo,'branch':branch,'cleanup_required':True,'transport_mode':mode})
        elif branch_mode=='append_existing_branch' and mode=='request_file':
            branch=str(invocation.get('target_branch') or invocation.get('base_ref') or '')
            if not branch: raise RuntimeError(f'{node_id}: append_existing_branch requires target_branch')
            status,head_sha=ensure_append_request(repo,branch,path,payload,message)
        elif branch_mode=='ephemeral_pull_request_branch' and mode=='pull_request':
            branch=deterministic_branch(request,node_id); base_ref=str(invocation.get('base_ref') or 'main')
            status,head_sha,pr_number,pr_url=ensure_pull_request_request(repo,base_ref,branch,path,payload,message,f"Runtime request {request['workflow_id']} g{request['generation']}",'Controller-approved Webactueel runtime request. Do not merge this PR; the guarded runtime workflow reads the request from the PR head and writes its result back to the same branch.')
            temporary_branches.append({'repository':repo,'branch':branch,'cleanup_required':True,'transport_mode':mode,'pull_request_number':pr_number,'cleanup_requires_controller_verified_head':True})
        else: raise RuntimeError(f'{node_id}: unsupported branch_mode {branch_mode!r} for mode {mode!r}')
        entry={'id':node_id,'status':status,'mode':mode,'repository':repo,'workflow':node['workflow'],'executor_workflow':node.get('executor_workflow'),'branch':branch,'head_sha':head_sha,'request_path':path,'event_id':event_id,'correlation':{'request_path':path,'head_sha':head_sha,'workflow':node['workflow'],'executor_workflow':node.get('executor_workflow'),'artifact_pattern':node.get('artifact_pattern'),'result':node.get('result'),'result_pattern':node.get('result_pattern')}}
        if pr_number is not None: entry['pull_request']={'number':pr_number,'url':pr_url,'request_head_sha':head_sha}
        results.append(entry)
    invoked=[i for i in results if i['status'] in {'invoked','duplicate_ignored'}]; waiting=[i for i in results if i['status']=='waiting_dependencies']; runtime_state='waiting' if invoked or waiting else 'validating'
    output={'schema_version':'1.0','workflow_id':request['workflow_id'],'generation':request['generation'],'idempotency_key':request['idempotency_key'],'registry_fingerprint':request['registry_fingerprint'],'request_sha256':request_sha256,'runtime_state':runtime_state,'return_to':'webactueel-workflow','nodes':results,'temporary_branches':temporary_branches,'next_action':'controller_readback_and_resume'}
    output_path.parent.mkdir(parents=True,exist_ok=True); output_path.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); print(json.dumps(output,indent=2,ensure_ascii=False)); return 0

if __name__=='__main__': raise SystemExit(main())
