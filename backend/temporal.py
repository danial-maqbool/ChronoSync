"""Deterministic English temporal resolution with explicit uncertainty."""
import calendar
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dateutil.relativedelta import relativedelta
from dateutil.tz import datetime_exists, datetime_ambiguous
import dateparser

DAYS = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
MONTHS = 'January February March April May June July August September October November December'.split()
MONTH = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
DAY = '(?:'+'|'.join(DAYS)+')'
NUMS = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'fifteen':15,'thirty':30}
DATE_PATTERN = re.compile(r'\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?|'+MONTH+r'\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?|\d{1,2}(?:st|nd|rd|th)?\s+'+MONTH+r'(?:\s+\d{4})?|day after tomorrow|tomorrow|today|yesterday|(?:next\s+)?'+DAY+r'|in\s+(?:\d+|'+ '|'.join(NUMS)+r')\s+(?:days?|weeks?|months?))\b',re.I)

def aware(value, zone):
    d = datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else value
    return d.replace(tzinfo=ZoneInfo(zone)) if d.tzinfo is None else d

def resolve(text, reference, settings):
    zone = settings.get('timezone','Asia/Karachi')
    ref = aware(reference, zone).astimezone(ZoneInfo(zone))
    lower = text.lower().replace('–','-').replace('—','-')
    out = {'start':None,'end':None,'all_day':False,'time_unknown':True,'timezone':zone,'source_timezone':None,'rrule':None,'warnings':[], 'explanation':[], 'reference_datetime':ref.isoformat(), 'temporal_expression':None}
    warnings, reasons = out['warnings'], out['explanation']
    if re.search(r'\b(sometime|around|approximately|maybe|possibly)\b|\bnext (week|month)\b',lower) and not re.search(r'(beginning|end|first|last) of|first business day|last working day|first '+DAY,lower):
        warnings.append('Date is not sufficiently specific.')
        return out
    explicit_zone = re.search(r'\b(UTC|GMT|Asia/[A-Za-z_]+|Europe/[A-Za-z_]+|America/[A-Za-z_]+)\b',text)
    source_zone = zone
    if explicit_zone:
        source_zone = explicit_zone[1]
        out['source_timezone'] = source_zone
        try:
            ref = ref.astimezone(ZoneInfo(source_zone))
        except Exception:
            warnings.append('Unresolved source timezone'); return out
    elif re.search(r'\b(?:EST|CST|PST|IST|BST|EDT|PDT)\b',text):
        warnings.append('Timezone abbreviation is ambiguous; choose an IANA timezone.'); return out
    # Corrections and reschedules choose the target, never the superseded date.
    working = lower
    moved = re.search(r'(?:moved (?:from .+? )?to|rescheduled to|postponed until|changed to|make it|instead(?! of),?)\s+(.+)',lower)
    if moved:
        working = moved[1]; reasons.append('Selected the corrected or rescheduled target.')
    elif 'instead of' in lower:
        working = lower.split('instead of')[0]
    elif re.search(r'\bnot\b|no longer',lower):
        correction = re.search(r'(?:not|no longer)\s+(?:on\s+)?'+DAY+r'[.,; -]+(?:it is\s+)?(.+)',lower)
        if correction:
            working = correction[1]; reasons.append('Excluded the negated date.')
        else:
            warnings.append('Negated date; no event should be scheduled.'); return out
    for word, number in NUMS.items():
        working = re.sub(r'\b'+word+r'\b',str(number),working)
    date = None
    end_date = None
    month_shift = ref + relativedelta(months=1)
    business = re.search(r'(first business day|last working day|end of (?:next|this) month|beginning of next week)',working)
    ordinal = re.search(r'first ('+DAY+r') of next month',working)
    if ordinal:
        date = month_shift.replace(day=1)
        date += timedelta(days=(DAYS.index(ordinal[1])-date.weekday())%7)
    elif business:
        phrase=business[1]
        if phrase=='beginning of next week':
            date=ref+timedelta(days=(7-ref.weekday()))
        else:
            base=month_shift if 'next' in working else ref
            date=base.replace(day=1 if phrase=='first business day' else calendar.monthrange(base.year,base.month)[1])
            if phrase in {'first business day','last working day'}:
                while date.weekday()>4:
                    date+=timedelta(days=1 if phrase=='first business day' else -1)
                reasons.append('Business days mean Monday–Friday; public holidays are not inferred.')
    match = DATE_PATTERN.search(working)
    if match and date is None:
        expr=match[0]; out['temporal_expression']=expr
        if expr in {'today','tomorrow','day after tomorrow','yesterday'}:
            date=ref+timedelta(days={'today':0,'tomorrow':1,'day after tomorrow':2,'yesterday':-1}[expr])
        elif re.fullmatch(r'(?:next )?'+DAY,expr):
            day=expr.split()[-1]; delta=(DAYS.index(day)-ref.weekday())%7
            if expr.startswith('next '):
                delta=(7-ref.weekday())+DAYS.index(day)
                reasons.append('Next weekday means that weekday in the next Monday-starting week.')
            date=ref+timedelta(days=delta)
        elif expr.startswith('in '):
            count=int(expr.split()[1]); unit=expr.split()[2]
            date=ref+(relativedelta(months=count) if unit.startswith('month') else timedelta(days=count*(7 if unit.startswith('week') else 1)))
        else:
            date=dateparser.parse(expr, languages=['en'], settings={'RELATIVE_BASE':ref.replace(tzinfo=None),'DATE_ORDER':('YMD' if re.fullmatch(r'\d{4}-\d{2}-\d{2}',expr) else settings.get('date_order','DMY')),'PREFER_LOCALE_DATE_ORDER':False,'PREFER_DATES_FROM':'current_period','RETURN_AS_TIMEZONE_AWARE':False})
            if date:
                date=date.replace(tzinfo=ZoneInfo(source_zone))
                if not re.search(r'\b\d{4}\b',expr):
                    reasons.append('Year inferred from the source reference year; no automatic one-year rollover.')
                if re.fullmatch(r'\d{1,2}/\d{1,2}(?:/\d{2,4})?',expr):
                    reasons.append('Numeric date interpreted using configured '+settings.get('date_order','DMY')+' order.')
    # Shared-month and full-date inclusive ranges become exclusive all-day DTEND.
    rng=re.search('('+MONTH+r')\s+(\d{1,2})\s*-\s*(\d{1,2})',working,re.I)
    if rng:
        month=next(i+1 for i,m in enumerate(MONTHS) if m.lower().startswith(rng[1][:3].lower()))
        try:
            date=ref.replace(month=month,day=int(rng[2])); end_date=date.replace(day=int(rng[3]))
        except ValueError:
            warnings.append('Invalid date range'); return out
    elif re.search(r'\b(through|between)\b',working):
        matches=list(DATE_PATTERN.finditer(working))
        if len(matches)>=2 and date:
            other=resolve(matches[-1][0],date.isoformat(),{**settings,'timezone':source_zone})
            if other['start']:
                end_date=aware(other['start'],source_zone)
    recurring=re.search(r'\b(every|monthly|annually)\b',working)
    if recurring:
        freq='DAILY'; extra=''
        wk=re.search(DAY,working)
        if 'weekday' in working:
            freq='WEEKLY'; extra=';BYDAY=MO,TU,WE,TH,FR'
            date=date or ref
            while date.weekday()>4: date+=timedelta(days=1)
        elif 'first' in working and wk:
            freq='MONTHLY'; extra=';BYDAY=1'+wk[0][:2].upper()
            date=ref.replace(day=1); date+=timedelta(days=(DAYS.index(wk[0])-date.weekday())%7)
            if date.date()<ref.date():
                date=month_shift.replace(day=1); date+=timedelta(days=(DAYS.index(wk[0])-date.weekday())%7)
        elif wk:
            freq='WEEKLY'; extra=';BYDAY='+wk[0][:2].upper()
        elif re.search(r'(?:2|two) weeks',working): freq='WEEKLY'; extra=';INTERVAL=2'
        elif 'month' in working:
            freq='MONTHLY'; daymatch=re.search(r'on the (\d{1,2})',working)
            if daymatch:
                day=int(daymatch[1]); extra=';BYMONTHDAY='+str(day)
                try:
                    date=ref.replace(day=day)
                    if date.date()<ref.date(): date=date+relativedelta(months=1)
                except ValueError:
                    warnings.append('Invalid monthly day'); return out
        elif 'annually' in working: freq='YEARLY'
        out['rrule']='FREQ='+freq+extra
        if date is None:
            warnings.append('Recurrence start date must be selected.'); return out
    if date is None:
        warnings.append('No specific calendar date could be resolved.'); return out
    date=date.replace(hour=0,minute=0,second=0,microsecond=0)
    clock=re.search(r'\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\b',working)
    military=re.search(r'\b(\d{1,2}):(\d{2})\b',working)
    bare=re.search(r'\bat\s+(\d{1,2})\b(?!\s*(?:am|pm|:))',working)
    time=None
    if clock:
        hour=int(clock[1]); minute=int(clock[2] or 0)
        if not 1<=hour<=12 or minute>59: warnings.append('Invalid clock time'); return out
        time=(hour%12+(12 if clock[3].startswith('p') else 0),minute)
    elif military:
        time=(int(military[1]),int(military[2]))
    elif 'noon' in working: time=(12,0)
    elif 'midnight' in working: time=(0,0)
    elif bare:
        warnings.append('AM/PM is missing; choose an exact time.')
    business_time='eod' if re.search(r'\beod\b|end of day',working) else ('cob' if re.search(r'\bcob\b|close of business',working) else None)
    if business_time:
        configured=settings.get(business_time)
        if configured: time=tuple(map(int,configured.split(':'))); reasons.append('Used configured '+business_time.upper()+' time.')
        else: warnings.append(business_time.upper()+' time is not configured.')
    if time is None and not warnings and settings.get('default_deadline_time') and re.search(r'due|deadline|submit|by\b',working):
        time=tuple(map(int,settings['default_deadline_time'].split(':'))); reasons.append('Time defaulted from deadline settings.')
    if time:
        try: date=date.replace(hour=time[0],minute=time[1])
        except ValueError: warnings.append('Invalid clock time'); return out
        out['time_unknown']=False
        if not datetime_exists(date) or datetime_ambiguous(date):
            warnings.append('DST transition makes this local time nonexistent or ambiguous.'); return out
        end=date+timedelta(minutes=settings.get('duration',60))
        reasons.append('End uses configured default duration unless an explicit end is present.')
        clocks=list(re.finditer(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b',working))
        if len(clocks)>=2 and re.search(r'\b(?:to|until)\b|\s-\s',working) and not moved:
            c=clocks[-1]; end=date.replace(hour=int(c[1])%12+(12 if c[3]=='pm' else 0),minute=int(c[2] or 0))
            if end<=date: warnings.append('End time is not after start; confirm overnight intent.')
    else:
        out['all_day']=not warnings
        end=(end_date or date).replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)
        reasons.append('Date only; exact time is unknown. All-day calendar representation requires approval.')
    if end_date and time: end=end_date.replace(hour=end.hour,minute=end.minute)
    if end<=date: warnings.append('End must be after start.')
    if date.date()<ref.date(): warnings.append('PAST_DATE_WARNING')
    out['start']=date.astimezone(ZoneInfo(zone)).isoformat()
    out['end']=end.astimezone(ZoneInfo(zone)).isoformat()
    reasons.insert(0,'Resolved against '+ref.isoformat()+'.')
    out['temporal_expression']=out['temporal_expression'] or text
    return out
