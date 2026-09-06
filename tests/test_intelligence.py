from backend.intelligence import extract, conflicts
from backend.db import DEFAULTS
from backend.calendars import MockCalendarProvider,export_ics
from backend.db import Store

def source(text): return {'id':'source','name':'Synthetic','created_at':'2026-09-03T10:00:00+05:00','source_timestamp':'2026-09-03T10:00:00+05:00','segments':[{'text':text}]}
def test_context():
    e=extract(source('Meeting tomorrow at 4 PM.'),DEFAULTS,[],[])[0]
    assert e['start'].startswith('2026-09-04T16:00')
    assert e['sources'][0]['evidence']=='Meeting tomorrow at 4 PM.'
    assert not extract(source('The conference took place on June 4.'),DEFAULTS,[],[])
    assert extract(source('The meeting is not Monday. It is Wednesday.'),DEFAULTS,[],[])[0]['start'].startswith('2026-09-09')

def test_change_duplicate_conflict():
    e=extract(source('Interview Tuesday at 3 PM.'),DEFAULTS,[],[])[0]; e['id']='old'
    n=extract(source('Interview moved to Thursday at 4 PM.'),DEFAULTS,[e],[])[0]
    assert n['related_ids']==['old'] and n['change_kind']=='RESCHEDULE'
    assert extract(source('Interview Tuesday at 3 PM.'),DEFAULTS,[e],[])[0]['duplicate_ids']==['old']
    n={**e,'id':'new'}
    assert conflicts(n,[e])[0]['severity']=='FULL_OVERLAP'

def test_calendar(tmp_path):
    s=Store(tmp_path); s.migrate(); p=MockCalendarProvider(s)
    e=extract(source('Meeting tomorrow at 4 PM.'),DEFAULTS,[],[])[0]; e.update(id='test',status='CONFIRMED')
    ident=p.create_event(e); e['title']='Changed'; p.update_event(ident,e)
    assert p.get_event(ident)['title']=='Changed'
    from icalendar import Calendar
    assert Calendar.from_ical(export_ics([e])).walk('VEVENT')[0]['SUMMARY']=='Changed'
    p.delete_event(ident); assert p.get_event(ident) is None
