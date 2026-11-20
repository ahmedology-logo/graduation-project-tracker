"""Tests for the Takharruj project-feature services."""
import sqlite3

import pytest

from project_features import ProjectService


@pytest.fixture

def service():
    connection = sqlite3.connect(":memory:")
    app_service = ProjectService(connection)
    app_service.initialize()
    connection.executemany(
        "INSERT INTO users(user_id, name, role, available) VALUES (?, ?, ?, ?)",
        [
            ("S1", "Leader", "student", 1),
            ("S2", "Member", "student", 1),
            ("S3", "Member Two", "student", 1),
            ("D1", "Supervisor", "supervisor", 1),
            ("D2", "Busy Supervisor", "supervisor", 0),
        ],
    )
    connection.commit()
    yield app_service
    connection.close()



def setup_project(service):
    team_id = service.create_team("S1", ["S2", "S3"])
    project_id = service.register_project(team_id, "Smart Campus", "A campus services platform")
    return team_id, project_id




def test_student_can_sign_in(service):
    assert service.sign_in("S1")["role"] == "student"




def test_unknown_account_cannot_sign_in(service):
    with pytest.raises(ValueError, match="Account not found"):
        service.sign_in("UNKNOWN")




def test_student_can_create_team_and_invite_members(service):
    team_id = service.create_team("S1", ["S2", "S3"])
    members = service.connection.execute(
        "SELECT student_id FROM team_members WHERE team_id = ? ORDER BY student_id", (team_id,)
    ).fetchall()
    assert [row[0] for row in members] == ["S1", "S2", "S3"]




def test_team_can_register_project_title_and_description(service):
    team_id = service.create_team("S1", ["S2"])
    project_id = service.register_project(team_id, "Project title", "Project description")
    project = service.connection.execute(
        "SELECT title, description FROM projects WHERE project_id = ?", (project_id,)
    ).fetchone()
    assert tuple(project) == ("Project title", "Project description")




def test_team_leader_can_request_available_supervisor(service):
    _, project_id = setup_project(service)
    service.request_supervision(project_id, "D1")
    row = service.connection.execute(
        "SELECT supervisor_id, supervision_status FROM projects WHERE project_id = ?", (project_id,)
    ).fetchone()
    assert tuple(row) == ("D1", "pending")




def test_unavailable_supervisor_is_rejected(service):
    _, project_id = setup_project(service)
    with pytest.raises(ValueError, match="not available"):
        service.request_supervision(project_id, "D2")




def test_team_leader_can_create_task_for_member_with_due_date(service):
    _, project_id = setup_project(service)
    task_id = service.create_task(project_id, "S1", "Build login page", "S2", "2026-12-01")
    task = service.connection.execute(
        "SELECT title, owner_id, due_date FROM tasks WHERE task_id = ?", (task_id,)
    ).fetchone()
    assert tuple(task) == ("Build login page", "S2", "2026-12-01")




def test_non_leader_cannot_create_task(service):
    _, project_id = setup_project(service)
    with pytest.raises(ValueError, match="Only the team leader"):
        service.create_task(project_id, "S2", "Unauthorized task", "S2", "2026-12-01")




def test_task_owner_must_be_in_team(service):
    _, project_id = setup_project(service)
    with pytest.raises(ValueError, match="team member"):
        service.create_task(project_id, "S1", "External task", "S9", "2026-12-01")




def test_task_due_date_must_be_iso_date(service):
    _, project_id = setup_project(service)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        service.create_task(project_id, "S1", "Invalid date task", "S2", "tomorrow")
