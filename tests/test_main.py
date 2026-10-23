import pytest
import json
from pathlib import Path
import tempfile
from datetime import datetime, timedelta
import os
from clocktail.main import TaskManager, Task, StatusEnum, TASK_MAX_DAYS, acquire_lock  # Assuming the main code is saved as task_manager.py

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
    manager.snooze_task(task, timedelta(minutes=-10))
    manager.load_tasks()
    task = manager.get_next_task()
    assert task.project.name == "Project 1"
    assert task.name == "Task 1"
    assert task.snooze_until is None

def test_get_next_task_snoozed_future(manager):
    project = manager.add_project("Project 1")
    task = manager.add_task(project, "Task 1")
    manager.snooze_task(task, timedelta(minutes=10))
    task = manager.get_next_task()
    assert task is None  # No task should be returned yet

def test_mark_task_as_done(manager):
    manager.add_task(manager.add_project("Project1"), "Task 1")
    task = manager.projects[0].tasks[0]
    manager.mark_task(task, StatusEnum.DONE)
    manager.load_tasks()
    task = manager.projects[0].tasks[0]
    assert task.status == StatusEnum.DONE

def test_snooze_task(manager):
    task = manager.add_task(manager.add_project("Project1"), "Task 1")
    manager.snooze_task(task, timedelta(minutes=10))
    manager.load_tasks()
    task: Task = manager.projects[0].tasks[0]
    assert task.status == StatusEnum.WAITING
    assert (task.snooze_until - datetime.now()) >= timedelta(minutes=9)

def test_edit_task(manager):
    task = manager.add_task(manager.add_project("Project1"), "Task 1")
    manager.edit_task(task, "Updated Task 1", "123")
    manager.load_tasks()
    assert manager.projects[0].tasks[0].name == "Updated Task 1"
    assert manager.projects[0].tasks[0].description == "123"

def test_task_has_creation_time(manager):
    task = manager.add_task(manager.add_project("Project1"), "Task 1")
    assert (datetime.now() - task.creation_time) < timedelta(minutes=1)
    assert task.completion_time is None
    manager.load_tasks()
    assert manager.projects[0].tasks[0].creation_time == task.creation_time

def test_completion_time_set_when_done(manager):
    task = manager.add_task(manager.add_project("Project1"), "Task 1")
    manager.mark_task(task, StatusEnum.DONE)
    assert (datetime.now() - task.completion_time) < timedelta(minutes=1)
    manager.load_tasks()
    assert manager.projects[0].tasks[0].completion_time == task.completion_time

def test_completion_time_cleared_when_not_done_anymore(manager):
    task = manager.add_task(manager.add_project("Project1"), "Task 1")
    manager.mark_task(task, StatusEnum.DONE)
    manager.mark_task(task, StatusEnum.RUNNING)
    assert task.completion_time is None
    manager.snooze_task(task, timedelta(minutes=10))
    assert task.completion_time is None

def test_old_done_task_is_deleted(manager):
    project = manager.add_project("Project1")
    fresh = manager.add_task(project, "Fresh")
    recent = manager.add_task(project, "Recently done")
    old = manager.add_task(project, "Long done")
    manager.mark_task(recent, StatusEnum.DONE)
    manager.mark_task(old, StatusEnum.DONE)
    old.completion_time = datetime.now() - timedelta(days=TASK_MAX_DAYS, seconds=1)
    assert old.can_be_deleted()
    assert not recent.can_be_deleted()
    assert not fresh.can_be_deleted()
    manager.save_tasks()
    manager.load_tasks()
    assert [t.name for t in manager.projects[0].tasks] == ["Fresh", "Recently done"]

def test_load_task_without_dates(manager):
    """Tasks saved before creation/completion times existed must still load."""
    with open(manager.backend_path, "w") as _f:
        json.dump([{
            "name": "Project1",
            "description": "",
            "creation_time": datetime.now().isoformat(),
            "tasks": [{
                "name": "Task 1",
                "description": "",
                "status": "done",
                "snooze_until": None,
            }],
        }], _f)
    manager.load_tasks()
    task = manager.projects[0].tasks[0]
    assert task.creation_time is not None
    assert task.completion_time is None
    assert not task.can_be_deleted()

def test_wake_up_task(manager):
    task = manager.add_task(manager.add_project("Project1"), "Task 1")
    manager.snooze_task(task, timedelta(hours=1))
    manager.wake_up_task(task)
    manager.load_tasks()
    task = manager.projects[0].tasks[0]
    assert task.status == StatusEnum.RUNNING
    assert task.snooze_until is None

def test_second_instance_cannot_take_lock(tmp_path):
    lock_path = tmp_path / "tasks.lock"
    first, _ = acquire_lock(lock_path)
    assert first is not None
    second, other_pid = acquire_lock(lock_path)
    assert second is None
    assert other_pid == str(os.getpid())
    first.close()
    third, _ = acquire_lock(lock_path)
    assert third is not None
    third.close()

def test_save_leaves_no_temp_file(manager):
    manager.add_task(manager.add_project("Project1"), "Task 1")
    assert [p.name for p in manager.backend_path.parent.iterdir()] == ["tasks.json"]
