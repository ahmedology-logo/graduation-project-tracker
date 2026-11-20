# Findings for the graduation-project user stories


## Static-analysis findings

Ruff and Pylint could not be executed in the build environment: neither was installed,
and package installation was blocked by unavailable network access. Therefore no rule
counts or Pylint score are claimed. Run the commands in `before.txt` locally to
capture real output.


## Code review findings (manual)

| Finding | Code smell / risk | Improvement |
|---|---|---|
| Multiple stories in a single feature flow | Mixed responsibilities if placed directly in Flask routes | Keep DB operations behind `ProjectService` methods |
| User IDs passed as raw strings | Primitive obsession / invalid IDs | Validate user existence and role before actions |
| Team invitations can duplicate or exceed capacity | Duplicate data / boundary issue | Deduplicate invite IDs and enforce a five-member limit |
| Supervisor selection can be stale | Invalid state / availability check | Check supervisor role and availability at request time |
| Task ownership can point outside the team | Broken authorization / inconsistent data | Verify task owner is a project team member |
| Task due date is free-form input | Invalid data | Parse and normalize ISO `YYYY-MM-DD` dates |

## Hidden-bug explanation

There is no intentionally hidden bug in the refactored implementation. The tests explicitly
cover the edge cases that are easy to miss: unavailable supervisors, non-leader task
creation, assigning a task to a non-member, and malformed due dates. These checks prevent
invalid records from being accepted instead of relying on the UI to behave correctly.
