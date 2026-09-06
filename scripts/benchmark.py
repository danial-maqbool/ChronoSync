import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.temporal import resolve
from backend.db import DEFAULTS

cases=json.loads(Path('benchmarks/temporal_cases.json').read_text(encoding='utf-8'))
results=[]
for case in cases:
    try:
        out=resolve(case['text'],'2026-09-03T10:00:00+05:00',{**DEFAULTS,**case.get('settings',{})})
        passed=all(out.get(k) and out[k].startswith(case[k]) for k in ['start','end','rrule'] if k in case) and (bool(out['warnings']) if case.get('review') else True)
        results.append({'text':case['text'],'passed':bool(passed),'expected':case,'actual':out})
    except Exception as exc: results.append({'text':case['text'],'passed':False,'error':str(exc)})
report={'reference':'2026-09-03T10:00:00+05:00','cases':len(results),'passed':sum(r['passed'] for r in results),'results':results}
report['accuracy']=report['passed']/report['cases']
Path('docs/validation').mkdir(parents=True,exist_ok=True)
Path('docs/validation/temporal-benchmark.json').write_text(json.dumps(report,indent=2))
print(f"{report['passed']}/{report['cases']} ({report['accuracy']:.1%})")
raise SystemExit(0 if report['passed']==report['cases'] else 1)

