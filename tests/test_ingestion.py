import io
from backend.ingestion import parse_source

def test_pdf():
    import pymupdf
    d=pymupdf.open(); p=d.new_page(); p.insert_text((70,70),'Exam October 5')
    assert parse_source('demo.pdf',d.tobytes())['segments'][0]['page']==1

def test_docx():
    from docx import Document
    d=Document(); d.add_paragraph('Meeting Friday'); b=io.BytesIO(); d.save(b)
    assert parse_source('demo.docx',b.getvalue())['segments'][0]['text']=='Meeting Friday'

def test_transcripts():
    for ext in ['srt','vtt']:
        s=parse_source('demo.'+ext,b'1\n00:18:42.000 --> 00:18:45.000\nProfessor Khan: Exam October 5\n')['segments'][0]
        assert s['speaker']=='Professor Khan' and s['start_timestamp']=='00:18:42.000'

def test_eml():
    s=parse_source('demo.eml',b'From: ali@example.test\nDate: Thu, 3 Sep 2026 14:00:00 +0500\nSubject: Meeting\nContent-Type: text/plain\n\nMeeting tomorrow.')['segments'][0]
    assert s['timestamp'].startswith('2026-09-03')

def test_chat():
    s=parse_source('chat.txt',b'03/09/2026, 14:31 - Ali: Meeting tomorrow at 4 PM')['segments'][0]
    assert s['sender']=='Ali' and s['timestamp'].startswith('2026-09-03')

def test_slack():
    s=parse_source('chat.json',b'[{"text":"Call tomorrow", "ts":"1788426000.0","user":"Ali"}]')['segments'][0]
    assert s['timestamp'] and s['sender']=='Ali'
