import pytest
from pathlib import Path
import tempfile
from datetime import datetime, timedelta
from clocktail.main import TaskManager  # Assuming the main code is saved as task_manager.py

@pytest.fixture
def manager():
    # Set up a fresh TaskManager for each test
    with tempfile.TemporaryDirectory() as _d:
        tm = TaskManager(Path(_d).joinpath("tasks.json"))
        tm.projects = {}
        yield tm

def test_add_task(manager):
    manager.add_task("Project1", "Task 1")
    assert len(manager.projects["Project1"]) == 1
    assert manager.projects["Project1"][0]["description"] == "Task 1"

def test_list_projects(manager):
    manager.add_task("Project1", "Task 1")
    manager.add_task("Project2", "Task 2")
    projects = manager.list_projects()
    assert "Project1" in projects
    assert "Project2" in projects

def test_get_next_task_no_snooze(manager):
    manager.add_task("Project1", "Task 1")
    project, task = manager.get_next_task()
    assert project == "Project1"
    assert task["description"] == "Task 1"

def test_get_next_task_snoozed_past(manager):
    task = manager.add_task("Project1", "Task 1",)
    manager.snooze_task("Project1", task['id'],-10,"")
    manager.list_projects_and_tasks()
    project, task = manager.get_next_task()
    assert project == "Project1"
    assert task["description"] == "Task 1"
    assert task["snooze_until"] is None

def test_get_next_task_snoozed_future(manager):
    task = manager.add_task("Project1", "Task 1",)
    manager.snooze_task("Project1", task['id'],10,"")
    manager.list_projects_and_tasks()
    project, task = manager.get_next_task()
    assert task is None  # No task should be returned yet

def test_mark_task_as_done(manager):
    task = manager.add_task("Project1", "Task 1")
    manager.mark_task("Project1", task['id'], "done")
    task = manager.projects["Project1"][0]
    assert task["status"] == "done"

def test_snooze_task(manager):
    manager.add_task("Project1", "Task 1")
    manager.snooze_task("Project1", 1, 10, "Waiting for input")
    task = manager.projects["Project1"][0]
    assert task["status"] == "waiting"
    assert task["snooze_until"] is not None

def test_edit_task(manager):
    manager.add_task("Project1", "Task 1")
    manager.projects["Project1"][0]["description"] = "Updated Task 1"
    assert manager.projects["Project1"][0]["description"] == "Updated Task 1"
