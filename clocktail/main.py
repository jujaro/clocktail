import os
import webbrowser
import json
from datetime import datetime, timedelta
from pathlib import Path

class TaskManager:
    def __init__(self, backend_path: Path):
        self.backend_path = backend_path
        self.projects = {}
        self.current_task_index = 0  # To track the rotation index
        self.load_tasks()

    def load_tasks(self):
        if os.path.exists(self.backend_path):
            with open(self.backend_path, "r") as file:
                self.projects = json.load(file)
        else:
            self.projects = {}

    def save_tasks(self):
        with open(self.backend_path, "w") as _f:
            json.dump(self.projects, _f, indent=4)

    def add_task(self, project_name, description, context=None, hyperlink=None):
        if project_name not in self.projects:
            self.projects[project_name] = []
        task = {
            "id": len(self.projects[project_name]) + 1,
            "description": description,
            "context": context,
            "hyperlink": hyperlink,
            "status": "running",
            "created_at": str(datetime.now()),
            "snooze_until": None,
        }
        self.projects[project_name].append(task)
        self.save_tasks()
        return task

    def list_projects(self):
        return list(self.projects.keys())

    def list_projects_and_tasks(self):
        for project, tasks in self.projects.items():
            print(f"Project: {project}")
            for task in tasks:
                snooze_info = f" (Snoozed until {task['snooze_until']})" if task['snooze_until'] else ""
                print(f"  [{task['status'].upper()}] {task['description']}{snooze_info}")

    def get_next_task(self):
        project_list = list(self.projects.items())
        for i in range(len(project_list)):
            project_name, tasks = project_list[self.current_task_index % len(project_list)]
            self.current_task_index = (self.current_task_index + 1) % len(project_list)
            for task in tasks:
                if task['status'] == "running":
                    return project_name, task
                if task['snooze_until'] and datetime.now() > datetime.fromisoformat(task['snooze_until']):
                    task['snooze_until'] = None
                    task['status'] = "running"
                    self.save_tasks()
                    return project_name, task
        return None, None

    def mark_task(self, project_name, task_id, status):
        for task in self.projects.get(project_name, []):
            if task['id'] == task_id:
                task['status'] = status
                task['snooze_until'] = None  # Clear snooze on status change
                self.save_tasks()
                return
        print("Task not found.")

    def snooze_task(self, project_name, task_id, duration_minutes, reason):
        for task in self.projects.get(project_name, []):
            if task['id'] == task_id:
                task['snooze_until'] = str(datetime.now() + timedelta(minutes=duration_minutes))
                task['status'] = "waiting"
                task['context'] = reason
                self.save_tasks()
                return
        print("Task not found.")

    def edit_task(self, project_name, task_id):
        for task in self.projects.get(project_name, []):
            if task['id'] == task_id:
                print("--- Edit Task ---")
                task['description'] = input(f"New Description (current: {task['description']}): ") or task['description']
                task['context'] = input(f"New Context (current: {task['context']}): ") or task['context']
                task['hyperlink'] = input(f"New Hyperlink (current: {task['hyperlink']}): ") or task['hyperlink']
                self.save_tasks()
                return
        print("Task not found.")

    def display_project_and_task(self, project_name, task):
        print(f"\nProject: {project_name}")
        for t in self.projects[project_name]:
            highlight = " -->" if t['id'] == task['id'] else ""
            print(f"  [{t['status'].upper()}] {t['description']}{t['snooze_until']}{highlight}")
        print(f"\nCurrent Task:")
        print(f"[{task['status'].upper()}] {task['description']}")
        if task['context']:
            print(f"Context: {task['context']}")
        if task['hyperlink']:
            print(f"Hyperlink: {task['hyperlink']}")


def main():
    manager = TaskManager(Path(__file__).parent.joinpath("taks.json"))

    while True:
        os.system("clear")
        project_name, task = manager.get_next_task()
        print("--- Clocktail CLI ---")
        if task:
            manager.display_project_and_task(project_name, task)
        print("--- Actions ---")
        print("1. Add Task")
        print("2. List Projects and Tasks")
        if task:
            print("3. Mark Task as Done")
            print("4. Snooze Task")
            print("5. Skip Task")
            print("6. Edit Task")
            if task['hyperlink']:
                print("7. Open Hyperlink")
        print("8. Exit")
        choice = input("Select an option: ")

        if choice == "1":
            print("--- Add Task ---")
            projects = manager.list_projects()
            if projects:
                print("Available Projects:")
                for idx, proj in enumerate(projects, 1):
                    print(f"{idx}. {proj}")
                project_choice = input("Select a project by number or press Enter to create a new project: ")
                if project_choice.isdigit() and 1 <= int(project_choice) <= len(projects):
                    project_name = projects[int(project_choice) - 1]
                else:
                    project_name = input("New Project Name: ")
            else:
                print("No existing projects.")
                project_name = input("New Project Name: ")

            description = input("Task Description: ")
            context = input("Context (optional): ")
            hyperlink = input("Hyperlink (optional): ")
            manager.add_task(project_name, description, context, hyperlink)
        elif choice == "2":
            manager.list_projects_and_tasks()
            input("Press Enter to continue...")
        elif task and choice == "3":
            manager.mark_task(project_name, task["id"], "done")
        elif task and choice == "4":
            duration = int(input("Duration to snooze (minutes): "))
            reason = input("Reason for snoozing: ")
            manager.snooze_task(project_name, task["id"], duration, reason)
        elif task and choice == "5":
            print("Skipping task...")
        elif task and choice == "6":
            manager.edit_task(project_name, task["id"])
        elif task and choice == "7" and task['hyperlink']:
            webbrowser.open(task['hyperlink'])
            input("Press Enter after viewing the hyperlink...")
        elif choice == "8":
            break
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main()
