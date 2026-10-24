"""At login: fetch the patient list in the background, so the journal assistant's picker is ready
the moment it opens instead of waiting for the record system then. Runs as the user (autostart).
Only health personnel get a list; for IT mode or emergency access the service just says no."""

import sys
import urllib.request

URL = "http://127.0.0.1:8000/api/journal/pasienter"


def main() -> int:
    # Straight to the local service, never through the web filter.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(URL, timeout=30) as response:
            response.read()
    except OSError:
        pass  # not logged in as health personnel, or the record system is down: the picker will say so
    return 0


if __name__ == "__main__":
    sys.exit(main())
