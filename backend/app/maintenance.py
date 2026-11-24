"""Scheduled maintenance. Run daily, e.g. `python -m app.maintenance purge` from cron."""
import sys

from .db import get_db
from .services import purge_all

if __name__ == "__main__":
    if sys.argv[1:] == ["purge"]:
        db = next(get_db())
        print(f"purged {purge_all(db)} expired records")
    else:
        print("usage: python -m app.maintenance purge")
