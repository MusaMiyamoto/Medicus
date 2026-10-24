"""Run the public web demo: python3 -m medicus.demo_server [port]

One process serves the Medicus web apps in demo mode (medicus/demo.py) and, under /helsenett, the
helsenett simulator with its synthetic patients. Everything it writes (the simulator's state, the
audit log) goes to a fresh temporary folder, removed when it stops. Synthetic data only.

Put it on the internet through a tunnel that forwards to 127.0.0.1, for example a Cloudflare quick
tunnel: cloudflared tunnel --url http://127.0.0.1:8080
"""

import os
import sys
import tempfile
from pathlib import Path


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    port = int(argv[0]) if argv else 8080
    folder = Path(tempfile.mkdtemp(prefix="medicus-demo-"))
    config = folder / "integrasjon.toml"
    config.write_text(f'modus = "simulert"\n\n[simulert]\nurl = "http://127.0.0.1:{port}/helsenett"\n\n'
                      '[journal]\nsystem = "helsenett"\n', encoding="utf-8")
    # Read by medicus.app when it is imported, so set before the import below.
    os.environ.pop("MEDICUS_DEV_IDENTITY", None)
    os.environ.update({"MEDICUS_DEMO": "1", "MEDICUS_WARMUP": "0", "MEDICUS_INTEGRASJON": str(config),
                       "MEDICUS_AUDIT_LOG": str(folder / "audit.jsonl")})

    import shutil

    import uvicorn

    from helsenett.sim.app import create_app
    from medicus.app import app

    app.mount("/helsenett", create_app(folder / "helsenett-sim.json"))
    print(f"Medicus-demo: http://127.0.0.1:{port}/demo  (data i {folder})", flush=True)
    try:
        # proxy_headers: behind the tunnel, cookies are marked Secure because the visitor uses https.
        uvicorn.run(app, host="127.0.0.1", port=port, proxy_headers=True, forwarded_allow_ips="127.0.0.1")
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
