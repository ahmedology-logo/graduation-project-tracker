# Refactoring / quality summary


## Before / after table

| Measure | Before | After |
|---|---|---|
| Ruff issues | Not measured (tool unavailable) | Not measured (tool unavailable) |
| Pylint score | Not measured (tool unavailable) | Not measured (tool unavailable) |
| Tests passing | Not measured | 10 passed (`pytest -q week5`) |
| Validation | Manual baseline not run | Service-level validation + SQLite tests |


## Pairing reflection (sample, 4 sentences)
The driver focused on implementing each service method while the navigator checked the story requirements and edge cases. We split the work into authentication, team/project creation, supervisor requests, and task assignment. Testing together helped catch invalid inputs such as unavailable supervisors and task owners who are not team members. Pair programming made the implementation easier to review and reduced the chance of leaving validation only to the interface.


## Important

The provided project archive currently uses a demo ID-based sign-in and has existing team/project/supervisor-request routes. These two lab files implement the requested behaviors as a separate, testable service layer; they are not wired into the existing Flask UI/routes yet.
