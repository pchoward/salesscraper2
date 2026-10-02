"""Decide whether a GitHub Actions run should scrape.

The morning cron is ``17 7 * * *`` (3:17 AM EDT). The backup cron is
``43 9 * * *``. The backup exits without scraping or committing when a
successful scrape already finished on today's US Eastern date. A run counts
as successful when ``scrape_health.json`` has a run for that Eastern date
and at least one store/part did not fail. workflow_dispatch always scrapes.
"""

import datetime
import os
import sys
from zoneinfo import ZoneInfo

from health import load_state

EASTERN = ZoneInfo("America/New_York")
BACKUP_CRON = "43 9 * * *"


def _eastern_date(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        stamp = value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
        return stamp.astimezone(EASTERN).date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            return datetime.date.fromisoformat(text)
        stamp = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=datetime.timezone.utc)
    return stamp.astimezone(EASTERN).date()


def _run_succeeded(run):
    results = run.get("results") if isinstance(run, dict) else None
    if not isinstance(results, dict) or not results:
        return False
    for result in results.values():
        if isinstance(result, dict) and not result.get("failed"):
            return True
    return False


def _run_eastern_day(run):
    if not isinstance(run, dict):
        return None
    stamped = _eastern_date(run.get("scanned_at"))
    if stamped is not None and run.get("scanned_at"):
        return stamped
    return _eastern_date(run.get("date"))


def already_succeeded_today(path="scrape_health.json", now=None):
    """True when today's Eastern date already has a non-failed scrape."""
    moment = now or datetime.datetime.now(EASTERN)
    if isinstance(moment, datetime.datetime):
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=EASTERN)
        today = moment.astimezone(EASTERN).date()
    else:
        today = moment
    state = load_state(path)
    for run in state.get("runs") or []:
        if _run_eastern_day(run) == today and _run_succeeded(run):
            return True
    return False


def gate_should_scrape(event_name, schedule, path="scrape_health.json", now=None):
    """False only for the backup cron after a successful Eastern-day scrape."""
    event = (event_name or "").strip()
    cron = " ".join((schedule or "").split())
    if event != "schedule" or cron != BACKUP_CRON:
        return True
    return not already_succeeded_today(path, now=now)


def write_gate_output(should_scrape, output_path=None):
    path = output_path if output_path is not None else os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"scrape={'true' if should_scrape else 'false'}\n")


def main(argv=None):
    event = os.environ.get("EVENT_NAME") or os.environ.get("GITHUB_EVENT_NAME") or ""
    schedule = os.environ.get("EVENT_SCHEDULE") or ""
    should = gate_should_scrape(event, schedule)
    write_gate_output(should)
    if should:
        print("scrape=true")
    else:
        print(
            "scrape=false Backup scrape skipped: a successful scrape already "
            "completed today (US Eastern)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
