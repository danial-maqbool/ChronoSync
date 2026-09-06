"""Run the built local app: python run.py. Uses only loopback by default."""

import os
import sys
import subprocess
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    os.chdir(root)
    venv = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if venv.exists() and Path(sys.executable).resolve() != venv.resolve():
        raise SystemExit(
            subprocess.call([str(venv), str(root / "run.py"), *sys.argv[1:]])
        )
    if not (root / "frontend/dist/index.html").exists():
        print("Build the frontend first: cd frontend && npm install && npm run build")
        raise SystemExit(1)
    import uvicorn
    from backend.app import create_app

    uvicorn.run(
        create_app(),
        host="0.0.0.0" if os.environ.get("CHRONOSYNC_MODE") == "cloud" else "127.0.0.1",
        port=int(os.environ.get("PORT", os.environ.get("CHRONOSYNC_PORT", "8765"))),
    )
