"""
MediKiosk Qwen 2.5 API Server Launcher
--------------------------------------
Launches the local Qwen 2.5 1.5B FastAPI model server on port 8000.
"""

import sys
import os
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import uvicorn

if __name__ == "__main__":
    scripts_dir = Path(__file__).resolve().parent
    repo_root = scripts_dir.parent
    base_dir = repo_root.parent

    candidate_paths = [
        repo_root / "qwen-compliance-api",
        repo_root / "qwen-compliance-api-main",
        base_dir / "qwen-compliance-api-main" / "qwen-compliance-api-main",
        base_dir / "qwen-compliance-api-main",
    ]

    qwen_dir = next((p for p in candidate_paths if p.exists() and (p / "app").exists()), None)

    if not qwen_dir:
        print("Error: Qwen directory not found in candidate paths:")
        for p in candidate_paths:
            print(f"  - {p}")
        sys.exit(1)
        
    os.chdir(str(qwen_dir))
    sys.path.insert(0, str(qwen_dir))
    
    print("=" * 60)
    print("Starting Local Qwen 2.5 1.5B Model Server on Port 8000...")
    print("Endpoint: http://localhost:8000/v1/chat/completions")
    print("Health Check: http://localhost:8000/health")
    print("=" * 60)
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="info")
