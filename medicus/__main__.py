import uvicorn

from .config import settings

if __name__ == "__main__":
    print(f"Medicus kjører på http://{settings.host}:{settings.port}")
    # One worker on purpose: unfinished notes, sessions and caches live in this process's memory.
    # (The audit log itself is safe with several writers: it locks the file.)
    uvicorn.run("medicus.app:app", host=settings.host, port=settings.port, workers=1)
