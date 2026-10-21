import uvicorn

from .config import settings

if __name__ == "__main__":
    print(f"Medicus kjører på http://{settings.host}:{settings.port}")
    uvicorn.run("medicus.app:app", host=settings.host, port=settings.port)
