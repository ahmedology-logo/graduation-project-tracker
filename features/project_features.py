"""Small, testable services for the Takharruj graduation-project stories."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Iterable


class ProjectService:
    """Implements team, project, supervision, login, and task operations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    def initialize(self) -> None:
        """Create the tables needed by these user stories."""
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student', 'supervisor')),
                available INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS teams (
                team_id INTEGER PRIMARY KEY AUTOINCREMENT,
                leader_id TEXT NOT NULL UNIQUE REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS team_members (
                team_id INTEGER NOT NULL REFERENCES teams(team_id),
                student_id TEXT NOT NULL UNIQUE REFERENCES users(user_id),
                PRIMARY KEY(team_id, student_id)
            );
            CREATE TABLE IF NOT EXISTS projects (
                project_id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL UNIQUE REFERENCES teams(team_id),
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                supervisor_id TEXT REFERENCES users(user_id),
                supervision_status TEXT NOT NULL DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS tasks (
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(project_id),
                title TEXT NOT NULL,
                owner_id TEXT NOT NULL REFERENCES users(user_id),
                due_date TEXT NOT NULL
            );
            """
        )
        self.connection.commit()



    def sign_in(self, user_id: str) -> dict[str, str]:
        """Return the account summary when an ID exists; otherwise raise ValueError."""
        user = self.connection.execute(
            "SELECT user_id, name, role FROM users WHERE user_id = ?", (user_id.strip(),)
        ).fetchone()
        if user is None:
            raise ValueError("Account not found")
        return dict(user)



    def create_team(self, leader_id: str, member_ids: Iterable[str] = ()) -> int:
        """Create a team with its leader and invited student members."""
        leader = self._require_user(leader_id, "student")
        members = list(dict.fromkeys(member_ids))
        if leader_id in members:
            members.remove(leader_id)
        if len(members) > 4:
            raise ValueError("A team can contain at most five students")
        team_id = self.connection.execute(
            "INSERT INTO teams(leader_id) VALUES (?)", (leader["user_id"],)
        ).lastrowid
        self.connection.execute(
            "INSERT INTO team_members(team_id, student_id) VALUES (?, ?)",
            (team_id, leader["user_id"]),
        )
        for member_id in members:
            self._require_user(member_id, "student")
            self.connection.execute(
                "INSERT INTO team_members(team_id, student_id) VALUES (?, ?)",
                (team_id, member_id),
            )
        self.connection.commit()
        return int(team_id)



    def register_project(self, team_id: int, title: str, description: str) -> int:
        """Register a project title and scope description for a team."""
        title = title.strip()
        description = description.strip()
        if not title or not description:
            raise ValueError("Project title and description are required")
        self._require_team_leader(team_id)
        project_id = self.connection.execute(
            "INSERT INTO projects(team_id, title, description) VALUES (?, ?, ?)",
            (team_id, title, description),
        ).lastrowid
        self.connection.commit()
        return int(project_id)



    def request_supervision(self, project_id: int, supervisor_id: str) -> None:
        """Send a pending supervision request to an available supervisor."""
        supervisor = self._require_user(supervisor_id, "supervisor")
        if not supervisor["available"]:
            raise ValueError("Supervisor is not available")
        project = self.connection.execute(
            "SELECT project_id FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise ValueError("Project not found")
        self.connection.execute(
            "UPDATE projects SET supervisor_id = ?, supervision_status = 'pending' "
            "WHERE project_id = ?",
            (supervisor_id, project_id),
        )
        self.connection.commit()



    def create_task(
        self, project_id: int, leader_id: str, title: str, owner_id: str, due_date: str
    ) -> int:
        """Create a task assigned to a project member with a valid due date."""
        title = title.strip()
        if not title:
            raise ValueError("Task title is required")
        try:
            parsed_due_date = date.fromisoformat(due_date)
        except ValueError as error:
            raise ValueError("Due date must use YYYY-MM-DD format") from error
        self._require_project_leader(project_id, leader_id)
        member = self.connection.execute(
            "SELECT 1 FROM team_members tm JOIN projects p ON p.team_id = tm.team_id "
            "WHERE p.project_id = ? AND tm.student_id = ?",
            (project_id, owner_id),
        ).fetchone()
        if member is None:
            raise ValueError("Task owner must be a project team member")
        task_id = self.connection.execute(
            "INSERT INTO tasks(project_id, title, owner_id, due_date) VALUES (?, ?, ?, ?)",
            (project_id, title, owner_id, parsed_due_date.isoformat()),
        ).lastrowid
        self.connection.commit()
        return int(task_id)



    def _require_user(self, user_id: str, role: str) -> sqlite3.Row:
        user = self.connection.execute(
            "SELECT * FROM users WHERE user_id = ? AND role = ?", (user_id, role)
        ).fetchone()
        if user is None:
            raise ValueError(f"User {user_id} is not a {role}")
        return user



    def _require_team_leader(self, team_id: int) -> str:
        team = self.connection.execute(
            "SELECT leader_id FROM teams WHERE team_id = ?", (team_id,)
        ).fetchone()
        if team is None:
            raise ValueError("Team not found")
        return str(team["leader_id"])



    def _require_project_leader(self, project_id: int, leader_id: str) -> None:
        project = self.connection.execute(
            "SELECT t.leader_id FROM projects p JOIN teams t ON t.team_id = p.team_id "
            "WHERE p.project_id = ?", (project_id,)
        ).fetchone()
        if project is None or project["leader_id"] != leader_id:
            raise ValueError("Only the team leader can create project tasks")
