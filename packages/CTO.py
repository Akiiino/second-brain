import datetime
import caldav
import icalendar
import pytz
import time
import argparse


def make_todos(calendar, date, dry_run):
    events = calendar.search(
        start=date,
        end=date + datetime.timedelta(days=1),
        event=True,
        expand=True,
        sort_keys=["dtstart"],
    )
    todos = calendar.search(
        start=date,
        end=date + datetime.timedelta(days=1),
        todo=True,
        expand=True,
        sort_keys=["dtstart"],
    )
    existing_todos = {todo.icalendar_component["summary"] for todo in todos}

    for event in events:
        event = event.icalendar_component

        if "description" not in event or "dtstart" not in event:
            continue

        time = event["dtstart"].dt.astimezone(tz=pytz.timezone("CET"))

        for i, line in enumerate(event["description"].split("\n")):
            if not line.startswith("[!] "):
                continue

            task = line.removeprefix("[!] ")

            if task in existing_todos:
                print(f'Task "{task}" already exists for this day ({time})')
                continue

            print(f'Creating task "{task}" at {time}')

            if dry_run:
                continue

            todo = calendar.save_todo(
                summary=task,
                dtstart=time + datetime.timedelta(seconds=i),
            )

            alarm = icalendar.Alarm(
                action="DISPLAY",
                trigger=icalendar.vDDDTypes(datetime.timedelta(0)),
            )
            alarm["trigger"].params = icalendar.Parameters(RELATED="START")

            todo.icalendar_component.add_component(alarm)
            todo.save()


def cleanup_todos(calendar, date, dry_run):
    todos = calendar.search(
        start=date - datetime.timedelta(weeks=52),
        end=date,
        todo=True,
        expand=True,
        sort_keys=["dtstart"],
    )

    for todo in todos:
        if "dtstart" not in todo.icalendar_component:
            continue

        task = todo.icalendar_component["summary"]
        print(f'Removing task "{task}"')

        if not dry_run:
            todo.delete()


parser = argparse.ArgumentParser(
    prog="Calendar Task Organizer",
    description=(
        "A tool for creating reocurring tasks automatically, "
        "based on calendar entries."
    ),
)

parser.add_argument("-c", "--calendar", required=True)
parser.add_argument("-u", "--username", required=True)
parser.add_argument("-p", "--password-file", required=True)
parser.add_argument("-d", "--day-lookahead", type=int, required=True)
parser.add_argument("-n", "--dry-run", action="store_true")

args = parser.parse_args()

with open(args.password_file, "r") as password_file:
    password = password_file.read().strip()

for _ in range(10):
    try:
        calendar = caldav.DAVClient(
            url=args.calendar,
            username=args.username,
            password=password,
        ).calendar(url=args.calendar)

        make_todos(
            calendar,
            datetime.date.today()
            + datetime.timedelta(days=args.day_lookahead),
            dry_run=args.dry_run,
        )

        cleanup_todos(
            calendar,
            datetime.date.today() - datetime.timedelta(days=1),
            dry_run=args.dry_run,
        )
        break
    except Exception:
        print("Waiting for the server...")
        time.sleep(10)
