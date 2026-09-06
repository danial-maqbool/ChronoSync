from datetime import datetime,timedelta
from zoneinfo import ZoneInfo

def examples():
    base=datetime.now(ZoneInfo('Asia/Karachi')).replace(hour=9,minute=0,second=0,microsecond=0)
    ref=base.isoformat()
    def day(n): return (base+timedelta(days=n)).strftime('%B %d %Y')
    return [
        ('University course outline.txt',f'Final project presentation on {day(3)} at 11 AM in Room B12.\nResearch assignment due {day(6)}.\nFinal exam on {day(10)} at 9 AM.',ref),
        ('Work meeting transcript.vtt','WEBVTT\n\n00:01:00.000 --> 00:01:08.000\n<v Sarah>Project review meeting tomorrow at 2 PM on Teams.\n\n00:02:00.000 --> 00:02:08.000\n<v Ahmed>Submit revised contract in three days.',ref),
        ('WhatsApp-style chat.txt',base.strftime('%d/%m/%Y, %H:%M')+' - Ali: Call with Hassan tomorrow at 10 AM.\n'+base.strftime('%d/%m/%Y, %H:%M')+' - Sara: Meeting sometime next week.',ref),
        ('Invoice payment notice.txt',f'Mandatory invoice payment due {day(2)} at 5 PM.',ref),
        ('Travel confirmation.txt',f'Flight departure on {day(14)} at 8 AM.\nHotel check-in on {day(14)} at 2 PM.',ref),
        ('Subscription renewal.txt',f'Your subscription renews on {day(20)}.',ref),
        ('Interview email.txt',f'Interview with Sarah on {day(4)} at 3 PM on Zoom.',ref),
        ('Project requirements.md',f'Submit project requirements by {day(7)}.\nTeam planning every Monday at 9 AM.\nDoctor appointment tomorrow at 2 PM.',ref),
    ]
