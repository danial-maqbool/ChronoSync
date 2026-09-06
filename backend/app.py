import asyncio
import hashlib
import io
import json
import csv
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from threading import RLock
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from backend.db import Store, DEFAULTS, now, uid
from backend.ingestion import parse_source
from backend.intelligence import extract, conflicts, similar, occurrences
from backend.temporal import aware
from backend.calendars import provider, snapshot, same_calendar, export_ics
from backend.schemas import Capture, EventInput, Action, TagInput, RuleInput

def create_app(directory=None):
    store=Store(directory)
    lock=RLock()
    def settings(): return store.get('settings','settings') or DEFAULTS.copy()
    def events(): return store.all('event')
    def required(kind,ident):
        item=store.get(kind,ident)
        if not item: raise HTTPException(404,'Record not found')
        return item
    def save_event(event,action,detail=None):
        event.setdefault('history',[]).append({'at':now(),'action':action,'detail':detail or {}})
        saved=store.put('event',event)
        store.audit(action,saved['id'],detail)
        return saved
    def notify(title,event_id=None):
        store.put('notification',{'title':title,'event_id':event_id,'read':False})
    def reminder_tick():
        with lock:
            current=datetime.now(timezone.utc)
            for e in events():
                if e.get('deleted') or e.get('status') not in {'CONFIRMED','SYNCED','SNOOZED'} or not e.get('start'): continue
                snooze=e.get('snoozed_until')
                if snooze and aware(snooze,'UTC')>current: continue
                if snooze:
                    notify('Snoozed reminder: '+e['title'],e['id'])
                    e.pop('snoozed_until',None)
                    e['status']='SYNCED' if e.get('external_id') else 'CONFIRMED'
                    store.put('event',e)
                    continue
                sent=e.get('delivered_reminders',[])
                targets=occurrences(e,current-timedelta(days=1),current+timedelta(days=366))
                changed=False
                for start,_ in targets:
                    if start<current-timedelta(days=1): continue
                    for offset in e.get('reminders',[]):
                        due=start-timedelta(minutes=offset)
                        marker=start.isoformat()+'/'+str(offset)+'/'+str(snooze or '')
                        if due<=current and marker not in sent and (current-due<timedelta(minutes=2) or snooze):
                            notify('Reminder: '+e['title'],e['id']); sent.append(marker); changed=True
                if changed:
                    e['delivered_reminders']=sent[-500:]
                    e.pop('snoozed_until',None)
                    if e['status']=='SNOOZED': e['status']='SYNCED' if e.get('external_id') else 'CONFIRMED'
                    store.put('event',e)
    async def scheduler():
        while True:
            try: await asyncio.to_thread(reminder_tick)
            except Exception:
                # Avoid private source text in logs; retry on the next tick.
                import logging
                logging.getLogger('chronosync').error('Reminder scheduler failed; retrying next minute')
            await asyncio.sleep(60)
    @asynccontextmanager
    async def lifespan(app):
        store.migrate()
        if not store.get('settings','settings'): store.put('settings',DEFAULTS)
        if not store.all('tag'):
            for name,color in [('Work','#45766e'),('University','#8265ad'),('Personal','#ba7b4b'),('Finance','#ad6471'),('Health','#609187'),('Travel','#5587aa'),('Family','#aa824f'),('Meeting','#4a817c'),('Deadline','#b76950'),('Renewal','#84783f'),('Interview','#8074a5')]:
                store.put('tag',{'name':name,'color':color,'archived':False})
        task=asyncio.create_task(scheduler())
        yield
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
    app=FastAPI(title='ChronoSync',lifespan=lifespan)
    app.state.store=store
    app.state.reminder_tick=reminder_tick
    @app.middleware('http')
    async def local_only(request:Request,call_next):
        host=request.headers.get('host','').split(':')[0]
        if host not in {'127.0.0.1','localhost','testserver'}:
            return Response('Local access only',403)
        if request.method not in {'GET','HEAD','OPTIONS'}:
            origin=request.headers.get('origin')
            if origin and origin not in {str(request.base_url).rstrip('/'),'http://127.0.0.1:5173','http://localhost:5173'}:
                return Response('Cross-origin write denied',403)
            if request.headers.get('sec-fetch-site')=='cross-site': return Response('Cross-site write denied',403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        return response

    def ingest(name,content,timestamp=None,reprocess=False):
        checksum=hashlib.sha256(content).hexdigest()
        previous=next((s for s in store.all('source') if s['checksum']==checksum and s['processing_status']=='COMPLETE'),None)
        if previous and not reprocess: return {**previous,'duplicate_source':True}
        source=store.put('source',{'name':Path(name).name,'checksum':checksum,'source_timestamp':timestamp,'language':'en','processing_status':'PROCESSING','segments':[],'text_length':0,'event_count':0})
        try:
            parsed=parse_source(name,content,settings()['date_order']=='DMY')
            source.update(parsed); source['text_length']=sum(len(s['text']) for s in parsed['segments'])
            old_version=next((s for s in reversed(store.all('source')) if s['name']==source['name'] and s['id']!=source['id'] and s['checksum']!=checksum),None)
            source['previous_version_id']=old_version['id'] if old_version else None
            candidates=extract(source,settings(),events(),store.all('rule'))
            for e in candidates:
                # Exact semantic duplicate attaches provenance to the same logical event.
                exact=[x for x in events() if x['id'] in e.get('duplicate_ids',[]) and x['title']==e['title'] and x.get('end')==e.get('end')]
                if len(exact)==1:
                    x=exact[0]; x['sources']+=e['sources']; save_event(x,'Duplicate Source Attached',{'source_id':source['id']}); continue
                if old_version and not e.get('change_kind'):
                    matched=[x for x in events() if any(s['source_id']==old_version['id'] for s in x.get('sources',[])) and similar(e['title'],x['title'])>.8 and x.get('start')!=e.get('start')]
                    if len(matched)==1: e.update(change_kind='RESCHEDULE',related_ids=[matched[0]['id']],status='NEEDS_REVIEW')
                e=save_event(e,'Event Extracted',{'source_id':source['id']})
                if e['importance']=='CRITICAL' or e.get('change_kind') or e.get('duplicate_ids'): notify('Review: '+e['title'],e['id'])
            if old_version:
                titles=[c['title'] for c in candidates]
                source['removed_event_ids']=[e['id'] for e in events() if any(s['source_id']==old_version['id'] for s in e.get('sources',[])) and not any(similar(e['title'],t)>.8 for t in titles)]
            source['processing_status']='COMPLETE'; source['event_count']=len(candidates)
            store.audit('Source Imported',detail={'source_id':source['id'],'event_count':len(candidates)})
        except Exception as exc:
            source['processing_status']='ERROR'; source['error']=str(exc)
        return store.put('source',source)

    @app.get('/api/health')
    def health(): return {'status':'ok','mode':'local','ai':'disabled'}
    @app.get('/api/workspace')
    def workspace():
        with lock:
            all_events=events()
            for e in all_events:
                e['conflicts']=conflicts(e,all_events,settings()['buffer']) if e.get('start') and not e.get('deleted') else []
                if e.get('rrule') and e.get('start'):
                    current=datetime.now(timezone.utc)
                    upcoming=[(a,b) for a,b in occurrences(e,current,current+timedelta(days=366)) if b>current]
                    if upcoming: e['next_occurrence']={'start':upcoming[0][0].isoformat(),'end':upcoming[0][1].isoformat()}
            return {'events':all_events,'sources':store.all('source'),'tags':store.all('tag'),'rules':store.all('rule'),'projects':store.all('project'),'audit':list(reversed(store.all('audit'))),'notifications':list(reversed(store.all('notification'))),'settings':settings(),'saved_views':store.all('view')}
    @app.post('/api/extraction/capture')
    def capture(body:Capture):
        with lock: return ingest(body.name+'.txt' if '.' not in body.name else body.name,body.text.encode(),body.source_timestamp.isoformat() if body.source_timestamp else None,body.reprocess)
    @app.post('/api/sources/import')
    async def upload(files:list[UploadFile]=File(...),source_timestamp:str=Form(''),reprocess:bool=Form(False)):
        if len(files)>50: raise HTTPException(400,'Import at most 50 files per batch')
        if source_timestamp:
            try: aware(source_timestamp,settings()['timezone'])
            except ValueError: raise HTTPException(422,'Invalid source timestamp')
        results=[]
        for file in files:
            content=await file.read(20*1024*1024+1)
            if len(content)>20*1024*1024: results.append({'name':file.filename,'processing_status':'ERROR','error':'File exceeds 20 MB'}); continue
            with lock: results.append(ingest(file.filename or 'source.txt',content,source_timestamp or None,reprocess))
        return results
    @app.get('/api/sources/{ident}')
    def source(ident:str): return required('source',ident)
    @app.delete('/api/sources/{ident}')
    def delete_source(ident:str):
        with lock:
            s=required('source',ident); s['segments']=[]; s['metadata']={}; s['processing_status']='DELETED'; s['text_length']=0
            for e in events():
                e['sources']=[x for x in e.get('sources',[]) if x['source_id']!=ident]; store.put('event',e)
            store.audit('Source Deleted',detail={'source_id':ident})
            return store.put('source',s)
    @app.get('/api/events')
    def list_events(q:str='',status:str='',importance:str='',tag:str=''):
        return [e for e in events() if not e.get('deleted') and (not q or q.lower() in json.dumps(e).lower()) and (not status or e['status']==status) and (not importance or e['importance']==importance) and (not tag or tag in e['tags'])]
    @app.post('/api/events')
    def new_event(body:EventInput):
        with lock:
            e=body.model_dump(mode='json')
            if not e['start'] or not e['end']: raise HTTPException(422,'Manual events require start and end')
            e.update(status='CONFIRMED',sync_state='NOT_SYNCED',sources=[],confidence=1,confidence_label='HIGH',history=[],deleted=False,resolution={'explanation':['Date explicitly entered by user.'],'warnings':[]})
            return save_event(e,'Event Created')
    @app.post('/api/events/{ident}/attachments')
    def attach_source(ident:str,body:dict):
        with lock:
            e=required('event',ident)
            if body.get('source_id'):
                s=required('source',body['source_id'])
                e['sources'].append({'source_id':s['id'],'name':s['name'],'evidence':'Manually attached source; no extraction inference.','segment':{}})
            elif body.get('url'):
                from urllib.parse import urlparse
                if urlparse(str(body['url'])).scheme not in {'https','http'}: raise HTTPException(422,'Use an HTTP or HTTPS URL')
                e.setdefault('attachments',[]).append({'url':str(body['url'])[:2000]})
            elif body.get('note'):
                e.setdefault('attachments',[]).append({'note':str(body['note'])[:10000]})
            else: raise HTTPException(422,'Choose a source, URL or note')
            return save_event(e,'Source Attached')
    @app.put('/api/events/{ident}')
    def edit_event(ident:str,body:EventInput,calendar:bool=True):
        with lock:
            old=required('event',ident); before=snapshot(old)
            e={**old,**body.model_dump(mode='json')}
            e['resolution']={**e.get('resolution',{}),'warnings':[],'explanation':e.get('resolution',{}).get('explanation',[])+['Date or details corrected manually.']}
            if e['status']=='NEEDS_REVIEW' and not e.get('change_kind') and not e.get('duplicate_ids'): e['status']='PROPOSED'
            if old.get('external_id'): e['sync_state']='OUT_OF_SYNC'
            e=save_event(e,'Event Edited',{'before':before,'after':snapshot(e)})
            if calendar and old.get('external_id'): return sync(e,confirmed_conflict=False)
            return e

    def sync(e,confirmed_conflict=False):
        if e.get('deleted') or e['status'] not in {'CONFIRMED','SYNCED','SNOOZED'}: raise HTTPException(409,'Approve the event before calendar synchronization')
        if not e.get('start') or not e.get('end') or e.get('resolution',{}).get('warnings') or e.get('duplicate_ids') or e.get('change_kind'): raise HTTPException(409,'Resolve date and duplicate/change warnings before synchronization')
        pname=e.get('provider') or settings()['provider']
        p=provider(pname,store)
        try:
            external=p.list_events()
            others=[x for x in external if x['id']!=e.get('external_id') and x.get('app_id')!=e['id']]
            collision=conflicts(e,events()+others,settings()['buffer'])
            if collision and not confirmed_conflict: raise HTTPException(409,{'message':'Calendar conflict requires an explicit Keep Both choice','conflicts':collision})
            if e.get('external_id'):
                current=p.get_event(e['external_id'])
                if current is None:
                    e['sync_state']='CALENDAR_MISSING'; store.put('event',e); raise HTTPException(409,'Calendar entry was deleted externally; disconnect the missing link before recreating')
                if e.get('calendar_snapshot') and not same_calendar(current,e['calendar_snapshot']):
                    e['sync_state']='OUT_OF_SYNC'; store.put('event',e); raise HTTPException(409,'External calendar change detected. Reconcile before updating.')
                ident=p.update_event(e['external_id'],e)
            else: ident=p.create_event(e)
            e.update(external_id=ident,provider=pname,sync_state='SYNCED',status='SYNCED',last_sync=now(),calendar_snapshot=snapshot(e))
            return save_event(e,'Calendar Synced' if not e.get('last_synced_before') else 'Calendar Updated',{'provider':pname})
        except HTTPException: raise
        except Exception as exc:
            e['sync_state']='SYNC_ERROR'; e['sync_error']=str(exc); store.put('event',e); notify('Calendar sync failed: '+e['title'],e['id'])
            raise HTTPException(503,str(exc))

    @app.post('/api/events/{ident}/action')
    def event_action(ident:str,body:Action):
        with lock:
            e=required('event',ident); action=body.action
            if action=='sync': return sync(e,body.confirm)
            if action=='reconcile':
                if not e.get('external_id'): return e
                try: other=provider(e['provider'],store).get_event(e['external_id'])
                except Exception as exc: raise HTTPException(503,str(exc))
                e['sync_state']='CALENDAR_MISSING' if other is None else ('SYNCED' if same_calendar(other,e) else 'OUT_OF_SYNC')
                e['external_change']=other
                if body.confirm:
                    if other is None:
                        e.pop('external_id',None); e['sync_state']='NOT_SYNCED'; e['status']='CONFIRMED'
                    else:
                        e.update(snapshot(other)); e['calendar_snapshot']=snapshot(other); e['sync_state']='SYNCED'
            elif action=='approve':
                if not e.get('start') or e.get('resolution',{}).get('warnings') or e.get('change_kind') or e.get('duplicate_ids'): raise HTTPException(409,'Edit unresolved details or review duplicate/change first')
                e['status']='CONFIRMED'
            elif action=='reject': e['status']='ARCHIVED'; e['rejected']=True
            elif action in {'complete','archive'}: e['status']='COMPLETED' if action=='complete' else 'ARCHIVED'
            elif action=='pin': e['pinned']=not e.get('pinned')
            elif action=='snooze':
                e['status']='SNOOZED'; e['snoozed_until']=(datetime.now(timezone.utc)+timedelta(minutes=body.snooze_minutes)).isoformat()
            elif action=='delete':
                if e.get('external_id') and not body.confirm: raise HTTPException(409,'Choose whether to delete the calendar copy')
                if body.calendar and e.get('external_id'):
                    try: provider(e['provider'],store).delete_event(e['external_id'])
                    except Exception as exc: raise HTTPException(503,str(exc))
                    e.pop('external_id',None); e['sync_state']='NOT_SYNCED'
                e['deleted']=True; e['deleted_at']=now()
            elif action=='restore': e['deleted']=False; e['status']='CONFIRMED' if e.get('start') else 'NEEDS_REVIEW'
            elif action=='keep_both':
                e.pop('duplicate_ids',None)
                e['status']='NEEDS_REVIEW' if e.get('resolution',{}).get('warnings') else 'PROPOSED'
            elif action=='merge':
                target=required('event',body.target_id or '')
                if target['id']==e['id']: raise HTTPException(400,'Cannot merge an event with itself')
                target['sources']+=e.get('sources',[]); target['tags']=list(dict.fromkeys(target['tags']+e['tags']))
                save_event(target,'Events Merged',{'merged_id':e['id']}); e['deleted']=True; e['merged_into']=target['id']
            elif action=='apply_change':
                if not body.confirm or not e.get('change_kind'): raise HTTPException(409,'Confirm the proposed change')
                target=required('event',body.target_id or (e.get('related_ids') or [''])[0])
                before=snapshot(target)
                if e['change_kind']=='CANCEL':
                    target['status']='CANCELLED'
                    if body.calendar and target.get('external_id'):
                        try: provider(target['provider'],store).delete_event(target['external_id'])
                        except Exception as exc: raise HTTPException(503,str(exc))
                        target.pop('external_id',None); target['sync_state']='NOT_SYNCED'
                    elif target.get('external_id'): target['sync_state']='OUT_OF_SYNC'
                else:
                    if not e.get('start') or e.get('resolution',{}).get('warnings'): raise HTTPException(409,'Resolve the new date first')
                    target.update({k:e[k] for k in ['start','end','all_day','timezone','rrule','resolution']})
                    if target.get('external_id'): target['sync_state']='OUT_OF_SYNC'
                target['sources']+=e['sources']; target=save_event(target,'Event '+('Cancelled' if e['change_kind']=='CANCEL' else 'Rescheduled'),{'before':before,'after':snapshot(target)})
                e['status']='ARCHIVED'; e['applied_to']=target['id']
                save_event(e,'Change Applied')
                if body.calendar and target.get('external_id') and e['change_kind']=='RESCHEDULE': return sync(target,False)
                return target
            elif action=='ignore_conflict': return sync(e,True)
            saved=save_event(e,'Event '+action.replace('_',' ').title())
            if action=='approve' and body.calendar: return sync(saved,body.confirm)
            return saved

    @app.post('/api/tags')
    def new_tag(body:TagInput):
        if any(t['name'].lower()==body.name.lower() for t in store.all('tag')): raise HTTPException(409,'Tag already exists')
        return store.put('tag',body.model_dump())
    @app.put('/api/tags/{ident}')
    def edit_tag(ident:str,body:TagInput):
        with lock:
            old=required('tag',ident)
            for e in events():
                if old['name'] in e['tags']:
                    e['tags']=[body.name if t==old['name'] else t for t in e['tags']]; save_event(e,'Tag Renamed')
            return store.put('tag',{**old,**body.model_dump()})
    @app.delete('/api/tags/{ident}')
    def delete_tag(ident:str):
        with lock:
            t=required('tag',ident)
            for e in events():
                if t['name'] in e['tags']: e['tags'].remove(t['name']); save_event(e,'Tag Removed')
            t['archived']=True; t['deleted']=True
            return store.put('tag',t)
    @app.post('/api/rules')
    def new_rule(body:RuleInput): return store.put('rule',body.model_dump())
    @app.put('/api/rules/{ident}')
    def edit_rule(ident:str,body:RuleInput): return store.put('rule',{**required('rule',ident),**body.model_dump()})
    @app.delete('/api/rules/{ident}')
    def delete_rule(ident:str): return store.put('rule',{**required('rule',ident),'enabled':False})
    @app.post('/api/projects')
    def project(body:TagInput): return store.put('project',body.model_dump())
    @app.put('/api/projects/{ident}')
    def edit_project(ident:str,body:TagInput): return store.put('project',{**required('project',ident),**body.model_dump()})
    @app.post('/api/settings/import')
    def import_preferences(body:dict):
        # Validate the full import before changing any records. No credentials accepted.
        try:
            if not set(body)<={'settings','tags','rules'}: raise ValueError('Unexpected backup fields')
            tag_values=[TagInput.model_validate({k:v for k,v in t.items() if k in TagInput.model_fields}) for t in body.get('tags',[])]
            rule_values=[RuleInput.model_validate({k:v for k,v in r.items() if k in RuleInput.model_fields}) for r in body.get('rules',[])]
            prefs=body.get('settings',{})
            if not set(prefs)<={'reminder_profiles','event_types'}: raise ValueError('Only profiles and event types can be imported')
            for values in prefs.get('reminder_profiles',{}).values(): EventInput(title='validate',reminders=values)
        except Exception as exc: raise HTTPException(422,str(exc))
        with lock:
            for t in tag_values:
                existing=next((x for x in store.all('tag') if x['name']==t.name),{})
                store.put('tag',{**existing,**t.model_dump()})
            for r in rule_values:
                existing=next((x for x in store.all('rule') if x['name']==r.name),{})
                store.put('rule',{**existing,**r.model_dump()})
            store.put('settings',{**settings(),**prefs})
            store.audit('Preferences Imported')
        return {'imported':True}
    @app.post('/api/views')
    def view(body:dict):
        if not body.get('name') or not isinstance(body.get('filters'),dict): raise HTTPException(422,'Name and filters required')
        return store.put('view',{'name':str(body['name'])[:100],'filters':body['filters']})
    @app.put('/api/settings')
    def update_settings(body:dict):
        allowed={'timezone','date_order','week_start','eod','cob','default_deadline_time','duration','buffer','provider','reminder_profiles','event_types','trash_retention_days'}
        if not set(body)<=allowed: raise HTTPException(422,'Unsupported setting; AI and automatic sync remain disabled')
        s={**settings(),**body}
        try:
            from zoneinfo import ZoneInfo
            import re
            ZoneInfo(s['timezone'])
            if s['date_order'] not in {'DMY','MDY'} or s['provider'] not in {'mock','outlook'}: raise ValueError('Invalid date order or provider')
            for k in ['eod','cob','default_deadline_time']:
                if s[k] and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',s[k]): raise ValueError('Use HH:MM')
            if not 1<=int(s['duration'])<=1440 or not 0<=int(s['buffer'])<=1440: raise ValueError('Invalid duration or buffer')
            for values in s['reminder_profiles'].values(): EventInput(title='validate',reminders=values)
        except Exception as exc: raise HTTPException(422,str(exc))
        return store.put('settings',s)
    @app.get('/api/calendar/test')
    def test_calendar(name:str='mock'):
        try: return {'connected':True,'provider':name,'event_count':len(provider(name,store).list_events()),'writes_performed':False}
        except Exception as exc: return {'connected':False,'provider':name,'error':str(exc),'writes_performed':False}
    @app.get('/api/calendar/occurrences')
    def calendar_occurrences(start:str,end:str):
        try:
            a=aware(start,settings()['timezone']); b=aware(end,settings()['timezone'])
            if b<=a or b-a>timedelta(days=400): raise ValueError('Choose a date range of 1–400 days')
        except Exception as exc: raise HTTPException(422,str(exc))
        result=[]
        for e in events():
            if e.get('deleted') or e['status'] not in {'CONFIRMED','SYNCED','SNOOZED'}: continue
            for s,t in occurrences(e,a,b):
                if s<b and t>a: result.append({**e,'start':s.isoformat(),'end':t.isoformat(),'series_start':e['start']})
        return result
    @app.post('/api/notifications/{ident}/read')
    def read_notification(ident:str): return store.put('notification',{**required('notification',ident),'read':True})
    @app.get('/api/export/{format}')
    def export(format:str):
        es=[e for e in events() if not e.get('deleted')]
        if format=='ics': return Response(export_ics(es),media_type='text/calendar',headers={'Content-Disposition':'attachment; filename=chronosync.ics'})
        if format=='settings': return Response(json.dumps({'settings':{k:v for k,v in settings().items() if k in {'reminder_profiles','event_types'}},'tags':store.all('tag'),'rules':store.all('rule')},indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename=chronosync-settings.json'})
        if format=='json': return Response(json.dumps(es,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename=chronosync.json'})
        fields=['title','start','end','type','importance','status','tags','location']
        def safe(v):
            text=', '.join(v) if isinstance(v,list) else str(v or '')
            return "'"+text if text.startswith(('=','+','-','@','\t','\r')) else text
        if format=='csv':
            out=io.StringIO(); writer=csv.writer(out); writer.writerow(fields)
            writer.writerows([[safe(e.get(k)) for k in fields] for e in es])
            return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=chronosync.csv'})
        if format=='xlsx':
            from openpyxl import Workbook
            wb=Workbook(); wb.remove(wb.active)
            groups={'Upcoming Events':[e for e in es if e['status'] in {'CONFIRMED','SYNCED','SNOOZED'}],'Completed Events':[e for e in es if e['status']=='COMPLETED'],'Needs Review':[e for e in es if e['status'] in {'PROPOSED','NEEDS_REVIEW'}],'Sources':store.all('source'),'Audit History':store.all('audit')}
            for title,rows in groups.items():
                ws=wb.create_sheet(title); keys=fields if 'Events' in title or title=='Needs Review' else (['name','type','created_at','event_count'] if title=='Sources' else ['created_at','action','event_id'])
                ws.append(keys)
                for row in rows: ws.append([safe(row.get(k)) for k in keys])
                ws.freeze_panes='A2'
                for col in ws.columns: ws.column_dimensions[col[0].column_letter].width=28
            data=io.BytesIO(); wb.save(data)
            return Response(data.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename=chronosync.xlsx'})
        raise HTTPException(404,'Unsupported export format')
    @app.post('/api/demo')
    def demo():
        from backend.demo import examples
        with lock: return [ingest(name,text.encode(),reference) for name,text,reference in examples()]

    dist=Path(__file__).resolve().parents[1]/'frontend'/'dist'
    if dist.exists():
        app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
        @app.get('/favicon.svg')
        def favicon(): return FileResponse(dist/'favicon.svg')
        @app.get('/{path:path}')
        def frontend(path:str):
            if path.startswith('api/'): raise HTTPException(404,'Unknown API endpoint')
            return FileResponse(dist/'index.html')
    return app
