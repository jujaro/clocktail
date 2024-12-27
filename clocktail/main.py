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


@dataclass
class Project:
    name: str
    status: str = "running"
    tasks: list[Task] = field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "status": self.status,
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
        for t in self.tasks:
            print(f"  [{t.status.upper()}] {t.name}")


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


class TaskManager:
    def __init__(self, backend_path: Path):
        self.backend_path = backend_path
        self.projects = []
        self.next_task_generator = self.gen_next_task()
        self.load_tasks()

    def load_tasks(self) -> None:
        if os.path.exists(self.backend_path):
            with open(self.backend_path, "r") as _f:
                self.projects = []
                for d_project in json.load(_f):
                    project = Project(d_project['name'], d_project['status'])
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
            json.dump(self.projects, _f, indent=4, default=lambda x: x.to_dict())

    def add_task(self, project: Project, name: str, description: str = "") -> Task:
        task = Task(name, description=description, status="running")
        project.add_task(task)
        self.save_tasks()
        return task

    def add_project(self, name: str) -> Project:
        project = Project(name,status="running")
        self.projects.append(project)
        return project

    def list_projects_and_tasks(self):
        result = []
        for project in self.projects:
            result.append(f"Project: {project.name}")
            for task in project.tasks:
                snooze_info = f" (Snoozed until {task['snooze_until']})" if task['snooze_until'] else ""
                result.append(f"  [{task['status'].upper()}] {task['description']}{snooze_info}")
        return "/n".join(result)

    def get_next_task(self) -> Task:
        return next(self.next_task_generator)

    def gen_next_task(self):
        while True:
            if (
                    not self.projects or
                    not [p for p in self.projects if p.tasks] or
                    not [t for p in self.projects for t in p.tasks if t.status == "running" or self.try_to_wake_up(t)]
            ):
                yield None
            for project in self.projects:
                for task in project.tasks:
                    if task.status == "waiting" and self.try_to_wake_up(task):
                        yield task
                    elif task.status == "running":
                        yield task

    def mark_task(self, task, status):
        task.status = status
        self.save_tasks()
        return

    def snooze_task(self, task: Task, duration_minutes):
        task.status = "waiting"
        task.snooze_until = datetime.now() + timedelta(minutes=duration_minutes)
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


def main():
    manager = TaskManager(Path(__file__).parent.joinpath("taks.json"))

    while True:
        os.system("clear")
        task = manager.get_next_task()
        if task:
            task.display_with_project()
        print("--- Actions ---")
        print("1. Add Task")
        print("2. List Projects and Tasks")
        if task:
            print("3. Mark Task as Done")
            print("4. Snooze Task")
            print("6. Edit Task")
        print("8. Exit")
        print("<enter> skips task")
        choice = input("Select an option:")

        if choice == "1":
            print("--- Add Task ---")
            print("Available Projects:")
            if not manager.projects:
                print("<No Projects>")
                project = None
            else:
                for idx, project in enumerate(manager.projects, 1):
                    print(f"{idx}. {project.name}")
                project_choice = input("Select a project by number or press Enter to create a new project: ")
                if project_choice.isdigit() and 1 <= int(project_choice) <= len(manager.projects):
                    project = manager.projects[int(project_choice) - 1]
                elif project_choice == "":
                    project = None
                else:
                    print("Invalid input:")
                    time.sleep(1)
                    continue
            if project is None:
                project = manager.add_project(input("New Project Name: "))
            name = input("Task Name: ")
            description = prompt_with_editor("")
            manager.add_task(project, name, description)
        elif choice == "2":
            manager.list_projects_and_tasks()
            input("Press Enter to continue...")
        elif task and choice == "3":
            manager.mark_task(task, "done")
        elif task and choice == "4":
            duration = int(input("Duration to snooze (minutes): "))
            manager.snooze_task(task, duration)
        elif task and choice == "6":
            manager.edit_task(
                task,
                input("Task Name <enter=unchanged>: ") or task.name,
                prompt_with_editor(task.description)
            )
        elif choice == "8":
            break
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main()
