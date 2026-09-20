from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r=client.get('/health'); assert r.status_code==200; assert r.json()['status']=='ok'

def test_triage_security():
    r=client.post('/ai/triage',json={'title':'Production credential leaked','body':'token exposed in logs'})
    assert r.status_code==200
    assert r.json()['priority']=='critical'
    assert r.json()['category']=='security'

def test_pr_review():
    r=client.post('/ai/pr-review',json={'title':'Change auth middleware','changed_files':4,'additions':100,'deletions':10})
    assert r.status_code==200
    assert r.json()['risk']=='high'

def test_experiment_summary():
    r=client.post('/ai/experiment-summary',json={'experiment':'x','metrics':{'accuracy':.92},'baseline':{'accuracy':.90}})
    assert r.status_code==200
    assert r.json()['improvements']==['accuracy']

def test_approval_flow():
    r=client.post('/approvals',json={'workflow':'test','summary':'approve me','payload':{'x':1}})
    assert r.status_code==200
    aid=r.json()['approval_id']
    r=client.post(f'/approvals/{aid}/decision',json={'status':'approved','decided_by':'tester'})
    assert r.status_code==200
    assert r.json()['status']=='approved'
