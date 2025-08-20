# clocktail


> "A system's performance is determined by its bottleneck." (The Goal by Eliyahu M. Goldratt)

- This CLI tool functions like a TODO list. Instead of only showing what is left to do, it rotates your attention among the tasks you are working on, ensuring you focus on a single task at a time.
- The idea is to work on the task presented by the tool until you either complete it or need to wait (e.g., waiting for a response). Then, you return to the tool to get the next task.
- For the sort of work that I do, tasks require bursts of work followed by long wait periods. Idle time can be used to progress on other tasks.
- You can input your current tasks in a hierarchy of projects and tasks.
- You can add as much context as you want for each project/task, so you have all the information you need when you return to it.
- Some tasks can be snoozed, so they only appear after a certain time.
- Tasks can be marked as running, waiting (snoozed), or done.

# How to run.
```bash
$ git clone https://github.com/jujaro/clocktail.git
$ cd clocktail
$ pip install -r requirements.txt
$ cd clocktail
$ python main.py
```
