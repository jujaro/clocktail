# clocktail. A scheduler for my time.

> "A system's performance is determined by its bottleneck." (The Goal by Eliyahu M. Goldratt)

- This CLI tool functions like a TODO list. Instead of only showing what is left to do, it rotates your attention among the tasks you are working on, ensuring you focus on a single task at a time.
- The idea is to work on the task presented by the tool until you either complete it or need to wait (e.g., waiting for a response). Then, you return to the tool to get the next task.
- For the sort of work that I do, tasks require bursts of work followed by long wait periods. Idle time can be used to progress on other tasks.
- The problem with frequent rotation between tasks is that you lose the context every time you switch. To help with this, you can write the context in the task to help you remember it next time you see it.
- You can input your current tasks in a hierarchy of projects and tasks.
- You can add as much context as you want for each project/task, so you have all the information you need when you return to it.
- Some tasks can be snoozed, so they only appear after a certain time.
- Tasks can be marked as running, waiting (snoozed), or done.

# How to run.
This project is managed with [uv](https://docs.astral.sh/uv/). Install it first if you don't have it:
```bash
$ curl -LsSf https://astral.sh/uv/install.sh | sh
```

Run from a clone (uv creates the virtual environment and installs dependencies automatically):
```bash
$ git clone https://github.com/jujaro/clocktail.git
$ cd clocktail
$ uv run clocktail
```

# How to install.
Install it as a global command (`clocktail`, or the short alias `ct`) that you can run from any folder:
```bash
$ make install        # same as: uv tool install --force --editable . && uv tool update-shell
$ ct
```
- The install is editable, so `git pull` or local edits take effect without reinstalling. Re-run `make install` only if dependencies change.
- The commands are placed in `~/.local/bin`; `uv tool update-shell` adds it to your `PATH` if needed (open a new terminal afterwards).
- Uninstall with `make uninstall`.

Only one instance can run at a time (it holds a lock on `~/.clocktail.lock`), so two terminals can't overwrite each other's changes to `~/.clocktail.json`.

# Development.
```bash
$ uv sync              # create .venv with all dependencies
$ uv run pytest        # run the tests (or: make test)
$ uv add <package>     # add a runtime dependency
$ uv add --dev <package>  # add a development dependency
```
