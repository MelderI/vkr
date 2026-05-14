from __future__ import annotations

from collections import defaultdict
from statistics import pstdev

from melder_schedule.models import ScheduleIssue, ScheduledLesson


def validate_schedule(lessons: list[ScheduledLesson]) -> list[ScheduleIssue]:
    issues: list[ScheduleIssue] = []
    issues.extend(find_duplicate_usage(lessons, "teacher"))
    issues.extend(find_duplicate_usage(lessons, "room"))
    issues.extend(find_group_conflicts(lessons))
    issues.extend(find_room_mismatches(lessons))
    return issues


def find_duplicate_usage(lessons: list[ScheduledLesson], resource: str) -> list[ScheduleIssue]:
    usage: dict[tuple[str, str], list[ScheduledLesson]] = defaultdict(list)
    for lesson in lessons:
        resource_id = lesson.teacher if resource == "teacher" else lesson.room.id
        usage[(resource_id, lesson.timeslot.id)].append(lesson)

    issues = []
    for (resource_id, slot_id), slot_lessons in usage.items():
        if len(slot_lessons) > 1:
            issues.append(
                ScheduleIssue(
                    severity="error",
                    code=f"{resource.upper()}_CONFLICT",
                    message=f"{resource_id} занят несколько раз в слот {slot_id}",
                    event_ids=tuple(lesson.event_id for lesson in slot_lessons),
                )
            )
    return issues


def find_group_conflicts(lessons: list[ScheduledLesson]) -> list[ScheduleIssue]:
    usage: dict[tuple[str, str], list[ScheduledLesson]] = defaultdict(list)
    for lesson in lessons:
        for group in lesson.groups:
            usage[(group, lesson.timeslot.id)].append(lesson)

    issues = []
    for (group, slot_id), slot_lessons in usage.items():
        if len(slot_lessons) > 1:
            issues.append(
                ScheduleIssue(
                    severity="error",
                    code="GROUP_CONFLICT",
                    message=f"Группа {group} занята несколько раз в слот {slot_id}",
                    event_ids=tuple(lesson.event_id for lesson in slot_lessons),
                )
            )
    return issues


def find_room_mismatches(lessons: list[ScheduledLesson]) -> list[ScheduleIssue]:
    issues = []
    for lesson in lessons:
        if lesson.room.capacity < lesson.estimated_students:
            issues.append(
                ScheduleIssue(
                    severity="error",
                    code="ROOM_CAPACITY",
                    message=(
                        f"Аудитория {lesson.room.name} вмещает {lesson.room.capacity}, "
                        f"нужно {lesson.estimated_students}"
                    ),
                    event_ids=(lesson.event_id,),
                )
            )
    return issues


def quality_metrics(lessons: list[ScheduledLesson]) -> dict[str, float]:
    teacher_day_pairs: dict[tuple[str, str], list[int]] = defaultdict(list)
    for lesson in lessons:
        teacher_day_pairs[(lesson.teacher, lesson.timeslot.day)].append(lesson.timeslot.pair)

    windows = 0
    daily_loads: list[int] = []
    for pairs in teacher_day_pairs.values():
        unique_pairs = sorted(set(pairs))
        daily_loads.append(len(unique_pairs))
        if len(unique_pairs) >= 2:
            windows += max(unique_pairs) - min(unique_pairs) + 1 - len(unique_pairs)

    return {
        "lessons": float(len(lessons)),
        "teacher_windows": float(windows),
        "teacher_daily_load_std": round(pstdev(daily_loads), 2) if len(daily_loads) > 1 else 0.0,
    }
