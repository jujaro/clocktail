#!/usr/bin/python3
from dataclasses import dataclass, field, asdict
from enum import Enum
import fcntl
import os
import sys
import json
from datetime import datetime, timedelta
import time
from pathlib import Path
from weakref import ref
import subprocess
import tempfile
import re
import shutil
from prompt_toolkit import HTML, print_formatted_text, prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import choice, clear
from prompt_toolkit.shortcuts.choice_input import ChoiceInput
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import Validator

# Projects should be deleted after this
PROJECT_MAX_DAYS=15
# Done tasks should be deleted after this
TASK_MAX_DAYS=3

STYLE = Style.from_dict({
    "project": "bold ansicyan",
    "task": "bold",
    "current": "bold ansiyellow",
    "running": "",
    "waiting": "ansiyellow",
    "done": "ansibrightblack strike",
    "dim": "ansibrightblack",
    "key": "bold ansimagenta",
    "placeholder": "ansibrightblack",
    "selected-option": "bold ansicyan",
})

def echo(template: str = "", *args) -> None:
    """Print styled text. `args` are HTML-escaped into the `{}` slots of `template`."""
    print_formatted_text(HTML(template).format(*args), style=STYLE)

def rule() -> None:
    echo("<dim>{}</dim>", "─" * min(shutil.get_terminal_size().columns, 80))

def ask(message: str | HTML, **kwargs) -> str:
    return prompt(HTML(message) if isinstance(message, str) else message, style=STYLE, **kwargs)

def pause(message: str = "Press any key to continue…") -> None:
    kb = KeyBindings()
    @kb.add("<any>")
    @kb.add("escape", eager=True)
    def _(event):
        event.app.exit(result="")
    ask(f"<dim>{message}</dim>", key_bindings=kb)

def pick(message: str, options: list):
    """Arrow-key selection list; Esc or Ctrl-C raises KeyboardInterrupt."""
    kb = KeyBindings()
    @kb.add("escape", eager=True)
    def _(event):
        event.app.exit(exception=KeyboardInterrupt())
    return choice(
        HTML(message),
        options=options,
        style=STYLE,
        key_bindings=kb,
        bottom_toolbar=" ↑↓ move · Enter select · Esc cancel ",
    )

NOT_EMPTY = Validator.from_callable(
    lambda text: bool(text.strip()),
    error_message="Can't be empty",
    move_cursor_to_end=True,
)

def format_until(dt: datetime) -> str:
    """Human readable future date, e.g. 'in 2h'."""
    seconds = int((dt - datetime.now()).total_seconds())
    if seconds <= 0:
        return "now"
    if seconds < 3600:
        return f"in {max(seconds // 60, 1)}m"
    if seconds < 86400:
        return f"in {seconds // 3600}h"
    return f"in {seconds // 86400}d"

def format_datetime(dt: datetime) -> str:
    """Human readable past date, e.g. '2026-09-18 08:31 (2d ago)'."""
    seconds = int((datetime.now() - dt).total_seconds())
    if seconds < 60:
        ago = "just now"
    elif seconds < 3600:
        ago = f"{seconds // 60}m ago"
    elif seconds < 86400:
        ago = f"{seconds // 3600}h ago"
    else:
        ago = f"{seconds // 86400}d ago"
    return f"{dt.strftime('%Y-%m-%d %H:%M')} ({ago})"

@dataclass
class Status:
    name: str
    icon: str
    text_repr :str

class StatusEnum(Enum):
    RUNNING = Status("running", "🏃", "[Running]")
    WAITING = Status("waiting", "⏰", "[Waiting]")
    DONE = Status("done", "✅", "[Done]")

    @classmethod
    def from_str(cls, status_str: str):
        for status in cls:
            if status.value.name == status_str.lower():
                return status
        raise ValueError(f"Unknown status: {status_str}")

@dataclass
class Task:
    name: str
    description: str
    status: StatusEnum
    snooze_until: datetime | None = None
    creation_time: datetime = field(default_factory=datetime.now)
    completion_time: datetime | None = None
    _project : ref | None = None

    @property
    def project(self):
        return self._project()

    def set_status(self, status: StatusEnum):
        """Set the status, keeping completion_time in sync."""
        self.status = status
        if status == StatusEnum.DONE:
            if self.completion_time is None:
                self.completion_time = datetime.now()
        else:
            self.completion_time = None

    def can_be_deleted(self) -> bool:
        return (
                self.status == StatusEnum.DONE and
                self.completion_time is not None and
                (datetime.now() - self.completion_time) > timedelta(days=TASK_MAX_DAYS)
        )

    def set_project(self, project):
        self._project = ref(project)

    def display(self):
        echo("{} <task>{}</task>", self.status.value.icon, self.name)
        echo("<dim>Created {}</dim>", format_datetime(self.creation_time))
        if self.completion_time:
            echo("<dim>Done {}</dim>", format_datetime(self.completion_time))
        if self.snooze_until:
            echo("<dim>Wakes up {}</dim>", format_until(self.snooze_until))
        if self.description.strip():
            echo()
            echo("{}", self.description.rstrip())

    def display_with_project(self):
        rule()
        self.project.display(current=self)
        rule()
        self.display()
        rule()


@dataclass
class Project:
    name: str
    creation_time: datetime = field(default_factory=datetime.now)
    description: str = ""
    tasks: list[Task] = field(default_factory=list)
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "creation_time": self.creation_time.isoformat(),
            "tasks": [
                {
                "name": task.name,
                "description": task.description,
                "status": task.status.name.lower(),
                "snooze_until": task.snooze_until.isoformat() if task.snooze_until else None,
                "creation_time": task.creation_time.isoformat(),
                "completion_time": (
                    task.completion_time.isoformat() if task.completion_time else None
                )
                }
                for task in self.tasks
                if not task.can_be_deleted()
            ]
        }

    def add_task(self, task: Task):
        task.set_project(self)
        self.tasks.append(task)

    def display(self, current: Task | None = None):
        echo("<project>{}</project>  <dim>created {}</dim>", self.name, format_datetime(self.creation_time))
        if self.description.strip():
            echo("{}", self.description.rstrip())
        for t in self.tasks:
            css = "current" if t is current else t.status.value.name
            wakes = f"  wakes up {format_until(t.snooze_until)}" if t.snooze_until else ""
            echo(
                "  {} {} <" + css + ">{}</" + css + "><dim>{}</dim>",
                "▶" if t is current else " ", t.status.value.icon, t.name, wakes,
            )

    def is_done(self) -> bool:
        for t in self.tasks:
            if t.status != StatusEnum.DONE:
                return False
        return True

    def can_be_deleted(self) -> bool:
        return (
                self.is_done() and
                (datetime.now() - self.creation_time) > timedelta(days=PROJECT_MAX_DAYS)
        )

def prompt_with_editor(text: str):
    editor = os.getenv("EDITOR", "vim")

    with tempfile.NamedTemporaryFile(suffix=".tmp", mode="r+", delete=False) as tmp_file:
        temp_filename = tmp_file.name

    with open(temp_filename, "w") as _f:
        _f.write(text)

    try:
        subprocess.run([editor, temp_filename])
        with open(temp_filename, "r") as _f:
            content = _f.read()
    finally:
        os.unlink(temp_filename)

    return content

DURATION_RE = re.compile(r"([0-9]+)([mhd])")

def prompt_duration() -> timedelta|None:
    str_input = ask(
        "<b>Snooze for:</b> ",
        placeholder=HTML("<placeholder>e.g. 30m, 2h, 1d (empty to cancel)</placeholder>"),
        completer=WordCompleter(["15m", "30m", "1h", "2h", "4h", "1d", "2d", "7d"]),
        validator=Validator.from_callable(
            lambda text: not text.strip() or bool(DURATION_RE.fullmatch(text.strip())),
            error_message="Use a number followed by m, h or d (e.g. 30m)",
            move_cursor_to_end=True,
        ),
        validate_while_typing=False,
    ).strip()
    if not str_input:
        return None
    number, letter = DURATION_RE.fullmatch(str_input).groups()
    number = int(number)
    match letter:
        case "m":
            return timedelta(minutes=number)
        case "h":
            return timedelta(hours=number)
        case "d":
            return timedelta(days=number)


class TaskManager:
    def __init__(self, backend_path: Path):
        self.backend_path = backend_path
        self.projects = []
        self.next_task_generator = self.gen_next_task()
        self.load_tasks()

    @property
    def running_projects(self):
        return [p for p in self.projects if not p.is_done()]

    def load_tasks(self) -> None:
        if os.path.exists(self.backend_path):
            with open(self.backend_path, "r") as _f:
                self.projects = []
                for d_project in json.load(_f):
                    project = Project(
                        name=d_project['name'],
                        creation_time=datetime.fromisoformat(
                            d_project.get('creation_time', datetime.now().isoformat())
                        ),
                        description=d_project.get('description', '')
                    )
                    for d_task in d_project['tasks']:
                        task = Task(
                            name=d_task['name'],
                            description=d_task['description'],
                            status=StatusEnum.from_str(d_task['status']),
                            snooze_until=(
                                datetime.fromisoformat(d_task['snooze_until'])
                                if d_task['snooze_until']
                                else None
                            ),
                            creation_time=datetime.fromisoformat(
                                d_task.get('creation_time', datetime.now().isoformat())
                            ),
                            completion_time=(
                                datetime.fromisoformat(d_task['completion_time'])
                                if d_task.get('completion_time')
                                else None
                            ),
                        )
                        project.add_task(task)
                    self.projects.append(project)
        else:
            self.projects = []

    def save_tasks(self) -> None:
        projects_to_keep = [p for p in self.projects if not p.can_be_deleted()]
        tmp_path = self.backend_path.with_name(self.backend_path.name + ".tmp")
        with open(tmp_path, "w") as _f:
            json.dump(projects_to_keep, _f, indent=4, default=lambda x: x.to_dict())
            _f.flush()
            os.fsync(_f.fileno())
        os.replace(tmp_path, self.backend_path)

    def add_task(self, project: Project, name: str, description: str = "") -> Task:
        task = Task(name, description=description, status=StatusEnum.RUNNING)
        project.add_task(task)
        self.save_tasks()
        return task

    def add_project(self, name: str, description:str = "") -> Project:
        project = Project(name, description=description, creation_time=datetime.now())
        self.projects.append(project)
        return project

    def display_projects_and_tasks(self) -> None:
        if not self.projects:
            echo("<dim>There are no projects yet.</dim>")
        for project in self.projects:
            project.display()
            echo()

    def status_summary(self) -> str:
        tasks = [t for p in self.projects for t in p.tasks]
        running = sum(t.status == StatusEnum.RUNNING for t in tasks)
        waiting = [t for t in tasks if t.status == StatusEnum.WAITING]
        done = sum(t.status == StatusEnum.DONE for t in tasks)
        waiting_info = f"{len(waiting)} waiting"
        next_wake = min((t.snooze_until for t in waiting if t.snooze_until), default=None)
        if next_wake:
            waiting_info += f" (next {format_until(next_wake)})"
        return f" {running} running · {waiting_info} · {done} done "

    def get_next_task(self) -> Task:
        return next(self.next_task_generator)

    def gen_next_task(self):
        while True:
            if (
                    not self.running_projects or
                    not [p for p in self.running_projects if p.tasks] or
                    not [t for p in self.running_projects for t in p.tasks if t.status == StatusEnum.RUNNING or self.try_to_wake_up(t)]
            ):
                yield None
            for project in self.running_projects:
                for task in project.tasks:
                    if task.status == StatusEnum.WAITING and self.try_to_wake_up(task):
                        yield task
                    elif task.status == StatusEnum.RUNNING:
                        yield task

    def mark_task(self, task: Task, status: StatusEnum):
        task.set_status(status)
        self.save_tasks()
        return

    def snooze_task(self, task: Task, duration:timedelta):
        task.set_status(StatusEnum.WAITING)
        task.snooze_until = datetime.now() + duration
        self.save_tasks()
        return

    def wake_up_task(self, task: Task):
        task.set_status(StatusEnum.RUNNING)
        task.snooze_until = None
        self.save_tasks()

    def edit_task(self, task: Task, name: str, description: str):
        task.name = name
        task.description = description
        self.save_tasks()

    def try_to_wake_up(self, task: Task) -> bool:
        if task.snooze_until and datetime.now() >= task.snooze_until:
            task.snooze_until = None
            task.set_status(StatusEnum.RUNNING)
            self.save_tasks()
            return True
        return False

    def edit_project(self, project: Project, name: str, description: str):
        project.name = name
        project.description = description
        self.save_tasks()

    def pick_project(self, allow_new: bool = True, filter=lambda p: True) -> Project | None:
        """Returns None when a new project should be created (or nothing can be picked)."""
        projects = [p for p in self.projects if filter(p)]
        if not projects:
            return None
        options = [
            (
                p,
                HTML("<project>{}</project> <dim>({} open)</dim>").format(
                    p.name, sum(t.status != StatusEnum.DONE for t in p.tasks)
                ),
            )
            for p in projects
        ]
        if allow_new:
            options.append((None, HTML("<b>+ New project</b>")))
        return pick("<b>Select a project:</b>", options)

    def pick_task(self, project: Project, filter=lambda t: t.status == StatusEnum.WAITING) -> Task | None:
        tasks_to_pick = [t for t in project.tasks if filter(t)]
        if not tasks_to_pick:
            return None
        options = [
            (
                t,
                HTML("{} {} <dim>{}</dim>").format(
                    t.status.value.icon,
                    t.name,
                    f"wakes up {format_until(t.snooze_until)}" if t.snooze_until else "",
                ),
            )
            for t in tasks_to_pick
        ]
        return pick("<b>Select a task:</b>", options)

def expand_task_name_flags(name: str) -> tuple[str,bool]:
    """We can add flags at the end of the task name after a backslash, for example:
        'Buy groceries \\SD" - adds a flag that this task doesn't need description (skup description step when adding the task)'
    """
    name, flag = name.split("\\", 1) if "\\" in name else (name, "")
    if flag and flag != "SD":
        print(f"Unknown flag: {flag}")
        time.sleep(2)
    return name.strip(), flag == "SD"

ACTIONS = [
    # (action, shortcut key, label, needs a current task)
    ("next", "enter", "Next task", False),
    ("add", "a", "Add task", False),
    ("add_advanced", "A", "Add task to another project", False),
    ("list", "l", "List projects and tasks", False),
    ("done", "d", "Mark task as done", True),
    ("snooze", "s", "Snooze task", True),
    ("edit", "e", "Edit task", True),
    ("edit_project", "p", "Edit project", True),
    ("wake", "w", "Wake up a snoozed task", False),
    ("exit", "x", "Exit", False),
]

def prompt_action(has_task: bool, status: str) -> str:
    kb = KeyBindings()
    options = []
    for action, key, label, needs_task in ACTIONS:
        if needs_task and not has_task:
            continue
        if key != "enter":
            kb.add(key)(lambda event, action=action: event.app.exit(result=action))
        if action == "next" and not has_task:
            label = "Refresh"
        options.append((action, HTML("<key>{}</key>  {}").format("↵" if key == "enter" else key, label)))
    return ChoiceInput(
        message=HTML("<b>What next?</b>"),
        options=options,
        default="next",
        style=STYLE,
        key_bindings=kb,
        bottom_toolbar=status,
        show_numbers=False,
    ).prompt()

def prompt_description(header: str) -> str:
    description = prompt_with_editor(header)
    if description.strip() in ("", header):
        return ""
    return description

def acquire_lock(lock_path: Path):
    """Returns (lock_file, None) on success; keep lock_file alive for the whole session.
    Returns (None, other_pid) if another instance holds the lock."""
    lock_file = open(lock_path, "a+")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.seek(0)
        pid = lock_file.read().strip()
        lock_file.close()
        return None, pid
    lock_file.truncate(0)
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file, None

def main():
    _backend_path = Path.home().joinpath(".clocktail.json")
    _lock, other_pid = acquire_lock(_backend_path.with_suffix(".lock"))
    if _lock is None:
        echo("<b>clocktail is already running</b> <dim>(pid {})</dim>. Close it before starting another one.", other_pid or "?")
        sys.exit(1)
    manager = TaskManager(_backend_path)
    task = manager.get_next_task()
    while True:
        clear()
        if task:
            task.display_with_project()
        else:
            echo("<dim>Nothing to work on right now. Add a task, or wait for a snoozed one to wake up.</dim>")
        echo()
        try:
            action = prompt_action(task is not None, manager.status_summary())
        except (KeyboardInterrupt, EOFError):
            break

        try:
            if action in ("add", "add_advanced"):
                if action == "add_advanced":
                    project = manager.pick_project()
                else:
                    project = task.project if task is not None else None
                if project is None:
                    project_name = ask("<b>Project name:</b> ", validator=NOT_EMPTY).strip()
                    project_description = prompt_description("Project Description:")
                    project = manager.add_project(project_name, project_description)
                name = ask(
                    HTML("<b>Task name for</b> <project>{}</project><b>:</b> ").format(project.name),
                    placeholder=HTML("<placeholder>end with \\SD to skip the description</placeholder>"),
                    validator=Validator.from_callable(
                        lambda text: bool(text.split("\\", 1)[0].strip()),
                        error_message="Can't be empty",
                        move_cursor_to_end=True,
                    ),
                )
                name, _skip_description = expand_task_name_flags(name)
                description = "" if _skip_description else prompt_description("Task Description:")
                new_task = manager.add_task(project, name, description)
                if task is None:
                    task = new_task
            elif action == "list":
                clear()
                manager.display_projects_and_tasks()
                pause()
            elif action == "done":
                manager.mark_task(task, StatusEnum.DONE)
                task = manager.get_next_task()
            elif action == "snooze":
                duration = prompt_duration()
                if duration:
                    manager.snooze_task(task, duration)
                    task = manager.get_next_task()
            elif action == "edit":
                manager.edit_task(
                    task,
                    ask("<b>Task name:</b> ", default=task.name, validator=NOT_EMPTY).strip(),
                    prompt_with_editor(task.description)
                )
            elif action == "edit_project":
                manager.edit_project(
                    task.project,
                    ask("<b>Project name:</b> ", default=task.project.name, validator=NOT_EMPTY).strip(),
                    prompt_with_editor(task.project.description)
                )
            elif action == "exit":
                break
            elif action == "wake":
                has_waiting = lambda t: t.status == StatusEnum.WAITING
                project = manager.pick_project(allow_new=False, filter=lambda p: any(map(has_waiting, p.tasks)))
                if project is None:
                    pause("There are no snoozed tasks. Press any key to continue…")
                    continue
                woken = manager.pick_task(project, filter=has_waiting)
                if woken:
                    manager.wake_up_task(woken)
                    task = woken
            elif action == "next":
                task = manager.get_next_task()
        except (KeyboardInterrupt, EOFError):
            continue

if __name__ == "__main__":
    main()
