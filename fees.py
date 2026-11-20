"""Tuition fee calculation for the Student Services App (refactored)."""

from dataclasses import dataclass
from enum import Enum


class StudentType(Enum):
    """Kinds of students that pay different fee rates."""

    REGULAR = 1
    STAFF_CHILD = 2
    SCHOLARSHIP = 3


@dataclass(frozen=True)
class Course:
    """A course the student registered for."""

    hours: int


HOUR_RATE = 350
HIGH_FEE_THRESHOLD = 6000
HIGH_FEE_REDUCTION = 200
SUMMER_FEE = 150

# Share of the hourly rate each student type pays.
RATE_FACTOR = {
    StudentType.REGULAR: 1.0,
    StudentType.STAFF_CHILD: 0.5,
    StudentType.SCHOLARSHIP: 0.0,
}

REPORT_LABEL = {
    StudentType.REGULAR: "Student fee",
    StudentType.STAFF_CHILD: "Staff child fee",
    StudentType.SCHOLARSHIP: "Scholarship fee",
}


def tuition_fee(courses, student_type, summer=False, discount=0, extras=()):
    """Return the total tuition fee for one student."""
    factor = RATE_FACTOR[student_type]
    total = sum(course.hours * HOUR_RATE * factor for course in courses)
    if total > HIGH_FEE_THRESHOLD:
        total -= HIGH_FEE_REDUCTION
    if summer:
        total += SUMMER_FEE
    return total - discount + sum(extras)


def fee_report(courses, student_type, summer=False, discount=0):
    """Return a text report for one student (no printing here)."""
    fee = tuition_fee(courses, student_type, summer, discount)
    lines = [f"{REPORT_LABEL[student_type]}: {fee}"]
    if fee > HIGH_FEE_THRESHOLD:
        lines.append("High fee")
    return "\n".join(lines)


def process_all(students):
    """Return {name: fee} for every student, including scholarship students."""
    return {
        student["name"]: tuition_fee(
            student["courses"],
            StudentType(student["type"]),
            student["summer"],
        )
        for student in students
    }
