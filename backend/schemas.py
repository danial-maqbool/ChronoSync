from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from datetime import datetime
from zoneinfo import ZoneInfo

class EventInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(min_length=1,max_length=200)
    start:datetime|None=None
    end:datetime|None=None
    timezone:str='Asia/Karachi'
    all_day:bool=False
    type:str='Task'
    importance:Literal['CRITICAL','HIGH','MEDIUM','LOW','NONE']='MEDIUM'
    tags:list[str]=Field(default_factory=list,max_length=30)
    reminders:list[int]=Field(default_factory=lambda:[1440,60],max_length=12)
    location:str=''
    description:str=''
    notes:str=''
    people:list[str]=Field(default_factory=list)
    organization:str=''
    rrule:str|None=None
    pinned:bool=False
    projects:list[str]=Field(default_factory=list)
    related_ids:list[str]=Field(default_factory=list)
    @field_validator('timezone')
    @classmethod
    def valid_zone(cls,v):
        try: ZoneInfo(v)
        except Exception: raise ValueError('Use a valid IANA timezone')
        return v
    @field_validator('reminders')
    @classmethod
    def valid_reminders(cls,v):
        if any(n<0 or n>525600 for n in v): raise ValueError('Reminder offsets must be between 0 and 525600 minutes')
        return sorted(set(v),reverse=True)
    @model_validator(mode='after')
    def times(self):
        for dt in [self.start,self.end]:
            if dt and dt.tzinfo is None: raise ValueError('Datetime must include a timezone offset')
        if self.start and self.end and self.end<=self.start: raise ValueError('End must be after start')
        if self.rrule:
            from dateutil.rrule import rrulestr
            import re
            if len(self.rrule)>300 or not re.fullmatch(r'[A-Z0-9=;,+-]+',self.rrule) or not self.rrule.startswith('FREQ='): raise ValueError('Invalid RRULE')
            if any(x in self.rrule for x in ['SECONDLY','MINUTELY','HOURLY','BYSECOND','BYMINUTE','BYHOUR']): raise ValueError('Recurrence must be daily or less frequent')
            rrulestr(self.rrule,dtstart=self.start)
        return self

class Capture(BaseModel):
    name:str=Field(default='Pasted message',min_length=1,max_length=200)
    text:str=Field(min_length=1,max_length=1000000)
    source_timestamp:datetime|None=None
    reprocess:bool=False

class Action(BaseModel):
    action:Literal['approve','sync','reject','complete','archive','snooze','delete','restore','merge','keep_both','apply_change','ignore_conflict','reconcile','pin']
    calendar:bool=False
    confirm:bool=False
    target_id:str|None=None
    snooze_minutes:int=Field(default=60,ge=1,le=525600)

class TagInput(BaseModel):
    name:str=Field(min_length=1,max_length=50)
    color:str=Field(default='#517d70',pattern=r'^#[0-9a-fA-F]{6}$')
    archived:bool=False

class RuleInput(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    priority:int=0
    enabled:bool=True
    conditions:dict=Field(default_factory=dict)
    actions:dict=Field(default_factory=dict)
    @model_validator(mode='after')
    def validate_rule(self):
        if not set(self.conditions)<={'contains','type','tags','source'}: raise ValueError('Unsupported rule condition')
        if not set(self.actions)<={'importance','tags','reminders'}: raise ValueError('Unsupported rule action')
        EventInput(title='validate',**self.actions)
        return self
