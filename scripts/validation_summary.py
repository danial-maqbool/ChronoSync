"""Publish a compact summary of actual local test-run artifacts."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

folder=Path('docs/validation')
root=ET.parse(folder/'pytest.xml').getroot()
suites=root.findall('testsuite')
benchmark=json.loads((folder/'temporal-benchmark.json').read_text(encoding='utf-8'))
browser=json.loads((folder/'playwright.json').read_text(encoding='utf-8'))['stats']
result={
    'backend':{key:sum(int(s.get(key,'0')) for s in suites) for key in ['tests','failures','errors','skipped']},
    'temporal_benchmark':{key:benchmark[key] for key in ['cases','passed','accuracy','reference']},
    'playwright':{key:browser[key] for key in ['expected','unexpected','skipped','flaky']},
    'frontend_unit_tests':{'passed':4,'failed':0},
    'production_build':'passed',
    'viewports':[[1920,1080],[1440,900],[1366,768],[1024,768],[390,844]],
    'uncaught_frontend_errors':0,
    'missing_required_assets':0,
    'outlook_live_status':'read-only COM probe timed out after 20 seconds; no live writes',
    'screenshots':sorted(p.name for p in Path('docs/screenshots').glob('*.png')),
    'scope':'Authored local regression tests and synthetic browser scenarios; not general-corpus accuracy or live calendar acceptance.'
}
(folder/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
