import pytest
from pathlib import Path
import tempfile
from datetime import datetime, timedelta
from clocktail.main import TaskManager, Task  # Assuming the main code is saved as task_manager.py

@pytest.fixture
def manager():
    # Set up a fresh TaskManager for each test
    with tempfile.TemporaryDirectory() as _d:
        tm = TaskManager(Path(_d).joinpath("tasks.json"))
        yield tm

def test_add_task(manager):
    project = manager.add_project("Project1")
    manager.add_task(project, "Task 1", "")
    assert len(manager.projects) == 1
    assert manager.projects[0].tasks[0].name == "Task 1"

def test_save_n_load(manager):
    project = manager.add_project("Project1")
    manager.add_task(project, "Task 1", "Desc 1") # Will save changes
    manager.projects = []
    manager.load_tasks()
    assert len(manager.projects) == 1
    assert manager.projects[0].tasks[0].name == "Task 1"
    assert manager.projects[0].tasks[0].description == "Desc 1"

def test_get_next_task(manager):
    project = manager.add_project("Project 1")
    manager.add_task(project, "Task 1")
    manager.add_task(project, "Task 2")
    project = manager.add_project("Project 2")
    manager.add_task(project, "Task 3")
    manager.add_task(project, "Task 4")
    task = manager.get_next_task()
    assert task.project.name == "Project 1"
    assert task.name == "Task 1"
    manager.get_next_task()
    manager.get_next_task()
    task = manager.get_next_task()
    assert task.project.name == "Project 2"
    assert task.name == "Task 4"
    task = manager.get_next_task()
    assert task.project.name == "Project 1"
    assert task.name == "Task 1"

def test_get_next_task_snoozed_past(manager):
    project = manager.add_project("Project 1")
    task = manager.add_task(project, "Task 1")
    manager.snooze_task(task, -10)
    manager.load_tasks()
    task = manager.get_next_task()
    assert task.project.name == "Project 1"
    assert task.name == "Task 1"
    assert task.snooze_until is None

def test_get_next_task_snoozed_future(manager):
    project = manager.add_project("Project 1")
    task = manager.add_task(project, "Task 1")
    manager.snooze_task(task, 10)
    task = manager.get_next_task()
    assert task is None  # No task should be returned yet

def test_mark_task_as_done(manager):
    manager.add_task(manager.add_project("Project1"), "Task 1")
    task = manager.projects[0].tasks[0]
    manager.mark_task(task, "done")
    manager.load_tasks()
    task = manager.projects[0].tasks[0]
    assert task.status == "done"

def test_snooze_task(manager):
    task = manager.add_task(manager.add_project("Project1"), "Task 1")
    manager.snooze_task(task, 10)
    manager.load_tasks()
    task: Task = manager.projects[0].tasks[0]
    assert task.status == "waiting"
    assert (task.snooze_until - datetime.now()) >= timedelta(minutes=9)

def test_edit_task(manager):
    task = manager.add_task(manager.add_project("Project1"), "Task 1")
    manager.edit_task(task, "Updated Task 1", "123")
    manager.load_tasks()
    assert manager.projects[0].tasks[0].name == "Updated Task 1"
    assert manager.projects[0].tasks[0].description == "123"

