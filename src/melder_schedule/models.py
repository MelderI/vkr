from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActivityType(str, Enum):
    LECTURE = "lecture"
    PRACTICE = "practice"
    CONSULTATION = "consultation"
    EXAM = "exam"


@dataclass(frozen=True)
class LessonRequest:
    """A normalized request that must be placed into the timetable."""

    id: str
    teacher: str
    semester: str
    subject: str
    activity_type: ActivityType
    groups: tuple[str, ...]
    source_kind: str
    hours: float
    required_slots: int
    required_room_type: str
    estimated_students: int


@dataclass(frozen=True)
class Room:
    id: str
    name: str
    room_type: str
    capacity: int


@dataclass(frozen=True)
class Timeslot:
    id: str
    day: str
    pair: int
    week_type: str = "every"


@dataclass(frozen=True)
class ScheduledLesson:
    request_id: str
    event_id: str
    teacher: str
    semester: str
    subject: str
    activity_type: ActivityType
    groups: tuple[str, ...]
    source_kind: str
    timeslot: Timeslot
    room: Room
    estimated_students: int


@dataclass(frozen=True)
class ScheduleIssue:
    severity: str
    code: str
    message: str
    event_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduleResult:
    lessons: list[ScheduledLesson]
    issues: list[ScheduleIssue]
    objective_value: int
    solver_name: str
