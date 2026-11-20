# Lab 6-style user-story implementation for Takharruj


## Files
- `week5/project_features.py`: service implementation for the five stories.
- `week5/test_project_features.py`: pytest tests (10 tests).
- `docs/week5/before.txt`: baseline tool commands/status.
- `docs/week5/findings.md`: code-review findings and hidden-bug discussion.
- `docs/week5/after.md`: before/after table and pairing reflection.


## Stories covered
1. Team leader creates tasks, assigns owners, and sets due dates.
2. Team requests supervision from an available supervisor.
3. Team registers project title and description.
4. Student creates a team and invites members.
5. Student signs in by existing account ID.


## Run tests
From the extracted folder:

```bash
python -m pytest -q week5
```

Expected result: **10 passed**.

## Run static analysis locally

```bash
python -m pip install ruff pylint pytest
ruff check week5/project_features.py week5/test_project_features.py --statistics
pylint week5/project_features.py week5/test_project_features.py
ruff format week5
python -m pytest -q week5
```

The linter output was not generated in this environment because Ruff/Pylint were not installed and network access blocked installation. Please run these commands on your own machine and paste the terminal output into `docs/week5/before.txt` before submission.

