#!/usr/bin/python3
from dataclasses import dataclass, field, asdict
import os
import json
from datetime import datetime, timedelta
import time
from pathlib import Path
from weakref import ref
import subprocess
import tempfile
import re

# Projects should be deleted after this
PROJECT_MAX_DAYS=15

@dataclass
class Task:
    name: str
    description: str
    status: str
    snooze_until: datetime | None = None
    _project : ref | None = None

    @property
    def project(self):
        return self._project()

    def set_project(self, project):
        self._project = ref(project)

    def display(self):
        print(f"\nTask:")
        print(f"[{self.status.upper()}] {self.name}")
        print(self.description)

    def display_with_project(self):
        print("="*80)
        self.project.display()
        print("="*80)
        self.display()
        print("="*80)

    def wake_up(self):
        self.status = "running"
        self.snooze_until = None
        self.project.save_tasks()


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
                "status": task.status,
                "snooze_until": task.snooze_until.isoformat() if task.snooze_until else None
                }
                for task in self.tasks
            ]
        }

    def add_task(self, task: Task):
        task.set_project(self)
        self.tasks.append(task)

    def display(self):
        print(f"\nProject: {self.name}")
        if self.description:
            print(self.description)
        for t in self.tasks:
            print(f"  [{t.status.upper()}] {t.name}")

    def is_done(self) -> bool:
        for t in self.tasks:
            if t.status != "done":
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

def prompt_duration() -> timedelta|None:
    def _invalid(i:str):
        print(f"Invalid input:{i}")
        time.sleep(2)

    str_input = input("Duration to snooze (suffix with m/h/d): ")
    mmatch = re.match("([0-9]+)([mhd])", str_input)
    if mmatch:
        number, letter = mmatch.groups()
        number = int(number)
        match letter:
            case "m":
                return timedelta(minutes=number)
            case "h":
                return timedelta(hours=number)
            case "d":
                return timedelta(days=number)
    _invalid(str_input)
    return None


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
                            status=d_task['status'],
                            snooze_until=(
                                datetime.fromisoformat(d_task['snooze_until'])
                                if d_task['snooze_until']
                                else None
                            ),
                        )
                        project.add_task(task)
                    self.projects.append(project)
        else:
            self.projects = []

    def save_tasks(self) -> None:
        with open(self.backend_path, "w") as _f:
            projects_to_keep = [p for p in self.projects if not p.can_be_deleted()]
            json.dump(projects_to_keep, _f, indent=4, default=lambda x: x.to_dict())

    def add_task(self, project: Project, name: str, description: str = "") -> Task:
        task = Task(name, description=description, status="running")
        project.add_task(task)
        self.save_tasks()
        return task

    def add_project(self, name: str, description:str = "") -> Project:
        project = Project(name, description=description, creation_time=datetime.now())
        self.projects.append(project)
        return project

    def list_projects_and_tasks(self) -> str:
        result = []
        for project in self.projects:
            result.append(f"Project: {project.name}")
            for task in project.tasks:
                snooze_info = f" (Snoozed until {task.snooze_until})" if task.snooze_until else ""
                result.append(f"  [{task.status.upper()}] {task.name}{snooze_info}")
        return "\n".join(result)

    def get_next_task(self) -> Task:
        return next(self.next_task_generator)

    def gen_next_task(self):
        while True:
            if (
                    not self.running_projects or
                    not [p for p in self.running_projects if p.tasks] or
                    not [t for p in self.running_projects for t in p.tasks if t.status == "running" or self.try_to_wake_up(t)]
            ):
                yield None
            for project in self.running_projects:
                for task in project.tasks:
                    if task.status == "waiting" and self.try_to_wake_up(task):
                        yield task
                    elif task.status == "running":
                        yield task

    def mark_task(self, task, status):
        task.status = status
        self.save_tasks()
        return

    def snooze_task(self, task: Task, duration:timedelta):
        task.status = "waiting"
        task.snooze_until = datetime.now() + duration
        self.save_tasks()
        return

    def edit_task(self, task: Task, name: str, description: str):
        task.name = name
        task.description = description
        self.save_tasks()

    def try_to_wake_up(self, task) -> bool:
        if task.snooze_until and datetime.now() >= task.snooze_until:
            task.snooze_until = None
            task.status = "running"
            self.save_tasks()
            return True
        return False

    def edit_project(self, project: Project, name: str, description: str):
        project.name = name
        project.description = description
        self.save_tasks()

    def pick_project(self) -> Project:
        while True:
            for idx, project in enumerate(self.projects, 1):
                print(f"{idx}. {project.name}")
            project_choice = input(
                "Select a project by number or press Enter to create a new project: ")
            if project_choice.isdigit() and 1 <= int(project_choice) <= len(self.projects):
                project = self.projects[int(project_choice) - 1]
            elif project_choice == "":
                project = None
            else:
                print("Invalid input:")
                time.sleep(1)
                continue
            return project

    def pick_task(self, project: Project, filter=lambda t: t.status == "waiting") -> Task:
        while True:
            tasks_to_pick = [t for t in project.tasks if filter(t)]
            if not tasks_to_pick:
                print("No tasks to pick")
                time.sleep(1)
                return None
            for idx, task in enumerate(tasks_to_pick, 1):
                print(f"{idx}. {task.name}")
            task_choice = input(
                "Select a task by number")
            if task_choice.isdigit() and 1 <= int(task_choice) <= len(tasks_to_pick):
                task = project.tasks[int(task_choice) - 1]
            else:
                print("Invalid input:")
                time.sleep(1)
                continue
            return task


def main():
    manager = TaskManager(Path(__file__).parent.joinpath("taks.json"))
    task = manager.get_next_task()
    while True:
        os.system("clear")
        if task:
            task.display_with_project()
        print("--- Actions ---")
        print("a - Add Task")
        print("l - List Projects and Tasks")
        if task:
            print("d - Mark Task as done")
            print("s - Snooze Task")
            print("e - Edit Task")
            print("p - Edit Project")
        print("x - Exit")
        print("<enter> skips task")
        choice = input("Select an option:")

        if choice.lower() == "ae" or choice.lower() == "a":
            print("--- Add Task ---")
            if choice.lower() == "ae":
                print("Available Projects:")
                if not manager.projects:
                    print("<There are no existing projects>")
                    project = None
                else:
                    project = manager.pick_project()
            else:
                project = task.project if task is not None else None
            if project is None:
                project = manager.add_project(
                    input("New Project Name: "),
                    prompt_with_editor("Project Description:")
                )
            name = input("Task Name:")
            description = prompt_with_editor("Task Description:")
            manager.add_task(project, name, description)
        elif choice.lower() == "l":
            print(manager.list_projects_and_tasks())
            input("Press Enter to continue...")
        elif task and choice.lower() == "d":
            manager.mark_task(task, "done")
            task = manager.get_next_task()
        elif task and choice.lower() == "s":
            duration = prompt_duration()
            if duration:
                manager.snooze_task(task, duration)
                task = manager.get_next_task()
        elif task and choice.lower() == "e":
            print(f"Current Task Name: {task.name}")
            manager.edit_task(
                task,
                input("Task Name <enter=unchanged>: ") or task.name,
                prompt_with_editor(task.description)
            )
        elif task and choice.lower() == "p":
            manager.edit_project(
                task.project,
                input("Project Name <enter=unchanged>: ") or task.project.name,
                prompt_with_editor(task.project.description)
            )
        elif choice.lower() == "x":
            break
        elif choice.lower() == "w":
            project = manager.pick_project()
            if project is None:
                print("No project selected")
                time.sleep(1)
                continue
            task = manager.pick_task(project,filter = lambda t:t.status == "waiting")
            if task:
                task.wake_up()
        elif choice == "":
            task = manager.get_next_task()
        else:
            print("Invalid choice. Try again.")
            time.sleep(1)

if __name__ == "__main__":
    main()
