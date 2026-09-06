from fastapi.testclient import TestClient
from backend.app import create_app

def test_full_lifecycle(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        assert c.get('/api/health').status_code==200
        r=c.post('/api/extraction/capture',json={'text':'Interview September 15 2026 at 3 PM.','source_timestamp':'2026-09-03T10:00:00+05:00'})
        assert r.json()['processing_status']=='COMPLETE',r.text
        e=c.get('/api/events').json()[0]; ident=e['id']
        assert c.post(f'/api/events/{ident}/action',json={'action':'sync'}).status_code==409
        assert c.post(f'/api/events/{ident}/action',json={'action':'approve','calendar':True}).status_code==200
        assert c.get('/api/events').json()[0]['sync_state']=='SYNCED'
        editable={k:e[k] for k in ['title','start','end','timezone','type','importance','tags','reminders','all_day','location','description']}
        editable['title']='Interview with Sarah'
        assert c.put(f'/api/events/{ident}',json=editable).status_code==200
        external=app.state.store.all('mock_calendar')[0]
        assert external['title']=='Interview with Sarah'
        assert c.post(f'/api/events/{ident}/action',json={'action':'complete'}).status_code==200
        assert c.post(f'/api/events/{ident}/action',json={'action':'delete'}).status_code==409
        assert c.post(f'/api/events/{ident}/action',json={'action':'delete','confirm':True,'calendar':True}).status_code==200
        assert c.post(f'/api/events/{ident}/action',json={'action':'restore'}).status_code==200
        assert not c.get('/api/events').json()[0].get('external_id')
        assert c.get('/api/export/ics').status_code==200
        assert len(c.get('/api/workspace').json()['audit'])>=6

def test_changes_and_duplicate(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        def capture(text):
            r=c.post('/api/extraction/capture',json={'text':text,'source_timestamp':'2026-09-03T10:00:00+05:00'}).json()
            assert r['processing_status']=='COMPLETE',r
        capture('Interview Tuesday at 3 PM.')
        e=c.get('/api/events').json()[0]
        capture('Interview moved to Thursday at 4 PM.')
        proposal=next(x for x in c.get('/api/events').json() if x.get('change_kind'))
        assert c.post('/api/events/'+proposal['id']+'/action',json={'action':'apply_change','confirm':True,'target_id':e['id']}).status_code==200
        capture('Interview has been cancelled.')
        proposal=next(x for x in c.get('/api/events').json() if x.get('change_kind')=='CANCEL')
        assert c.post('/api/events/'+proposal['id']+'/action',json={'action':'apply_change','confirm':True,'target_id':e['id']}).status_code==200
        assert next(x for x in c.get('/api/events').json() if x['id']==e['id'])['status']=='CANCELLED'

def test_batch_security_and_rules(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        assert c.post('/api/demo',headers={'origin':'https://evil.example'}).status_code==403
        assert c.post('/api/rules',json={'name':'Exams','conditions':{'type':'Exam'},'actions':{'importance':'CRITICAL','tags':['University']}}).status_code==200
        r=c.post('/api/sources/import',files=[('files',('bad.pdf',b'not a pdf')),('files',('good.txt',b'Exam October 5 2026'))]).json()
        assert r[0]['processing_status']=='ERROR' and r[1]['processing_status']=='COMPLETE'
        assert c.get('/api/events').json()[0]['importance']=='CRITICAL'
