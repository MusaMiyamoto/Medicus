import os

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("MEDICUS_SIM_PORT", "8100"))
    print(f"Helsenett-simulator kjører på http://127.0.0.1:{port}")
    uvicorn.run("helsenett.sim.app:make_app", factory=True, host="127.0.0.1", port=port)
