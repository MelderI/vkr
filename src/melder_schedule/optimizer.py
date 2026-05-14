from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from melder_schedule.models import (
    LessonRequest,
    Room,
    ScheduleIssue,
    ScheduleResult,
    ScheduledLesson,
    Timeslot,
)


@dataclass(frozen=True)
class Event:
    id: str
    request: LessonRequest
    index: int


@dataclass(frozen=True)
class Candidate:
    event: Event
    timeslot: Timeslot
    room: Room
    penalty: int


def optimize_schedule(
    requests: Iterable[LessonRequest],
    rooms: list[Room],
    timeslots: list[Timeslot],
    *,
    time_limit_seconds: int = 20,
) -> ScheduleResult:
    request_list = list(requests)
    try:
        return optimize_with_ortools(
            request_list,
            rooms,
            timeslots,
            time_limit_seconds=time_limit_seconds,
        )
    except ImportError:
        return optimize_with_backtracking(request_list, rooms, timeslots)


def expand_events(requests: list[LessonRequest]) -> list[Event]:
    return [
        Event(id=f"{request.id}-{idx + 1}", request=request, index=idx + 1)
        for request in requests
        for idx in range(request.required_slots)
    ]


def compatible_rooms(request: LessonRequest, rooms: list[Room]) -> list[Room]:
    compatible = [
        room
        for room in rooms
        if room.room_type == request.required_room_type
        and room.capacity >= request.estimated_students
    ]
    if compatible:
        return compatible
    return [
        room
        for room in rooms
        if room.capacity >= request.estimated_students
    ]


def candidate_penalty(request: LessonRequest, room: Room, timeslot: Timeslot) -> int:
    room_waste = max(0, room.capacity - request.estimated_students)
    late_pair_penalty = max(0, timeslot.pair - 4) * 3
    lonely_day_risk = 1 if timeslot.pair in {1, 5} else 0
    return room_waste + late_pair_penalty + lonely_day_risk


def optimize_with_ortools(
    requests: list[LessonRequest],
    rooms: list[Room],
    timeslots: list[Timeslot],
    *,
    time_limit_seconds: int,
) -> ScheduleResult:
    from ortools.sat.python import cp_model

    events = expand_events(requests)
    model = cp_model.CpModel()
    variables: dict[tuple[str, str, str], cp_model.IntVar] = {}

    for event in events:
        room_options = compatible_rooms(event.request, rooms)
        if not room_options:
            return infeasible_result(events, f"Нет аудитории для {event.request.subject}")
        for slot in timeslots:
            for room in room_options:
                key = (event.id, slot.id, room.id)
                variables[key] = model.NewBoolVar(f"x_{event.id}_{slot.id}_{room.id}")

    for event in events:
        model.AddExactlyOne(
            variables[(event.id, slot.id, room.id)]
            for slot in timeslots
            for room in compatible_rooms(event.request, rooms)
        )

    for slot in timeslots:
        for teacher in sorted({event.request.teacher for event in events}):
            model.Add(
                sum(
                    variables[(event.id, slot.id, room.id)]
                    for event in events
                    if event.request.teacher == teacher
                    for room in compatible_rooms(event.request, rooms)
                )
                <= 1
            )

        all_groups = sorted({group for event in events for group in event.request.groups})
        for group in all_groups:
            model.Add(
                sum(
                    variables[(event.id, slot.id, room.id)]
                    for event in events
                    if group in event.request.groups
                    for room in compatible_rooms(event.request, rooms)
                )
                <= 1
            )

        for room in rooms:
            model.Add(
                sum(
                    variables[(event.id, slot.id, room.id)]
                    for event in events
                    if (event.id, slot.id, room.id) in variables
                )
                <= 1
            )

    objective_terms = []
    for event in events:
        for slot in timeslots:
            for room in compatible_rooms(event.request, rooms):
                objective_terms.append(
                    variables[(event.id, slot.id, room.id)]
                    * candidate_penalty(event.request, room, slot)
                )
    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    status = solver.Solve(model)

    if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        return infeasible_result(events, "CP-SAT не нашел допустимое расписание")

    lessons: list[ScheduledLesson] = []
    for event in events:
        for slot in timeslots:
            for room in compatible_rooms(event.request, rooms):
                if solver.BooleanValue(variables[(event.id, slot.id, room.id)]):
                    lessons.append(to_scheduled_lesson(event, slot, room))
    return ScheduleResult(
        lessons=lessons,
        issues=[],
        objective_value=int(solver.ObjectiveValue()),
        solver_name="OR-Tools CP-SAT",
    )


def optimize_with_backtracking(
    requests: list[LessonRequest],
    rooms: list[Room],
    timeslots: list[Timeslot],
) -> ScheduleResult:
    events = expand_events(requests)
    domains: dict[str, list[Candidate]] = {}
    issues: list[ScheduleIssue] = []

    for event in events:
        room_options = compatible_rooms(event.request, rooms)
        candidates = [
            Candidate(
                event=event,
                timeslot=slot,
                room=room,
                penalty=candidate_penalty(event.request, room, slot),
            )
            for slot in timeslots
            for room in room_options
        ]
        candidates.sort(key=lambda item: (item.penalty, item.timeslot.pair, item.room.capacity))
        if not candidates:
            issues.append(
                ScheduleIssue(
                    severity="error",
                    code="NO_ROOM",
                    message=f"Нет подходящей аудитории для {event.request.subject}",
                    event_ids=(event.id,),
                )
            )
        domains[event.id] = candidates

    if issues:
        return ScheduleResult([], issues, objective_value=0, solver_name="CSP backtracking")

    assignments: dict[str, Candidate] = {}
    used_teacher_slots: set[tuple[str, str]] = set()
    used_group_slots: set[tuple[str, str]] = set()
    used_room_slots: set[tuple[str, str]] = set()
    nodes_left = 15_000

    ordered_events = sorted(events, key=lambda event: (len(domains[event.id]), event.request.teacher))

    def search(position: int) -> bool:
        nonlocal nodes_left
        nodes_left -= 1
        if nodes_left <= 0:
            return False
        if position == len(ordered_events):
            return True

        event = ordered_events[position]
        for candidate in domains[event.id]:
            if conflicts(candidate, used_teacher_slots, used_group_slots, used_room_slots):
                continue
            place(candidate, assignments, used_teacher_slots, used_group_slots, used_room_slots)
            if search(position + 1):
                return True
            remove(candidate, assignments, used_teacher_slots, used_group_slots, used_room_slots)
        return False

    if not search(0):
        repaired = repair_assignments(ordered_events, domains)
        if repaired is None:
            return ScheduleResult(
                lessons=[],
                issues=[
                    ScheduleIssue(
                        severity="error",
                        code="INFEASIBLE",
                        message="Не удалось построить расписание для выбранного набора заявок",
                    )
                ],
                objective_value=0,
                solver_name="CSP backtracking/repair",
            )
        assignments = repaired

    lessons = [
        to_scheduled_lesson(candidate.event, candidate.timeslot, candidate.room)
        for candidate in assignments.values()
    ]
    return ScheduleResult(
        lessons=sorted(lessons, key=lambda lesson: (lesson.timeslot.day, lesson.timeslot.pair, lesson.teacher)),
        issues=[],
        objective_value=sum(candidate.penalty for candidate in assignments.values()),
        solver_name="CSP backtracking/repair",
    )


def repair_assignments(
    events: list[Event],
    domains: dict[str, list[Candidate]],
    *,
    max_iterations: int = 8_000,
) -> dict[str, Candidate] | None:
    assignments: dict[str, Candidate] = {}

    for event in events:
        candidate = min(
            domains[event.id],
            key=lambda option: (assignment_conflicts(option, assignments), option.penalty),
        )
        assignments[event.id] = candidate

    for _ in range(max_iterations):
        conflicted = conflicted_event_ids(assignments)
        if not conflicted:
            return assignments

        event_id = max(conflicted, key=lambda item: event_conflict_count(item, assignments))
        current = assignments[event_id]
        best = min(
            domains[event_id],
            key=lambda option: (
                replacement_conflicts(event_id, option, assignments),
                option.penalty,
            ),
        )
        if replacement_conflicts(event_id, best, assignments) > event_conflict_count(event_id, assignments):
            return None
        assignments[event_id] = best

        if assignments[event_id] == current and event_conflict_count(event_id, assignments) > 0:
            return None

    return None


def assignment_conflicts(candidate: Candidate, assignments: dict[str, Candidate]) -> int:
    conflicts_count = 0
    for other in assignments.values():
        if candidates_conflict(candidate, other):
            conflicts_count += 1
    return conflicts_count


def replacement_conflicts(
    event_id: str,
    candidate: Candidate,
    assignments: dict[str, Candidate],
) -> int:
    return assignment_conflicts(
        candidate,
        {
            other_event_id: other
            for other_event_id, other in assignments.items()
            if other_event_id != event_id
        },
    )


def conflicted_event_ids(assignments: dict[str, Candidate]) -> set[str]:
    conflicted: set[str] = set()
    items = list(assignments.items())
    for idx, (event_id, candidate) in enumerate(items):
        for other_event_id, other in items[idx + 1 :]:
            if candidates_conflict(candidate, other):
                conflicted.add(event_id)
                conflicted.add(other_event_id)
    return conflicted


def event_conflict_count(event_id: str, assignments: dict[str, Candidate]) -> int:
    candidate = assignments[event_id]
    return replacement_conflicts(event_id, candidate, assignments)


def candidates_conflict(left: Candidate, right: Candidate) -> bool:
    if left.timeslot.id != right.timeslot.id:
        return False
    if left.event.request.teacher == right.event.request.teacher:
        return True
    if left.room.id == right.room.id:
        return True
    return bool(set(left.event.request.groups) & set(right.event.request.groups))


def conflicts(
    candidate: Candidate,
    used_teacher_slots: set[tuple[str, str]],
    used_group_slots: set[tuple[str, str]],
    used_room_slots: set[tuple[str, str]],
) -> bool:
    slot_id = candidate.timeslot.id
    request = candidate.event.request
    if (request.teacher, slot_id) in used_teacher_slots:
        return True
    if (candidate.room.id, slot_id) in used_room_slots:
        return True
    return any((group, slot_id) in used_group_slots for group in request.groups)


def place(
    candidate: Candidate,
    assignments: dict[str, Candidate],
    used_teacher_slots: set[tuple[str, str]],
    used_group_slots: set[tuple[str, str]],
    used_room_slots: set[tuple[str, str]],
) -> None:
    slot_id = candidate.timeslot.id
    request = candidate.event.request
    assignments[candidate.event.id] = candidate
    used_teacher_slots.add((request.teacher, slot_id))
    used_room_slots.add((candidate.room.id, slot_id))
    for group in request.groups:
        used_group_slots.add((group, slot_id))


def remove(
    candidate: Candidate,
    assignments: dict[str, Candidate],
    used_teacher_slots: set[tuple[str, str]],
    used_group_slots: set[tuple[str, str]],
    used_room_slots: set[tuple[str, str]],
) -> None:
    slot_id = candidate.timeslot.id
    request = candidate.event.request
    assignments.pop(candidate.event.id, None)
    used_teacher_slots.remove((request.teacher, slot_id))
    used_room_slots.remove((candidate.room.id, slot_id))
    for group in request.groups:
        used_group_slots.remove((group, slot_id))


def to_scheduled_lesson(event: Event, timeslot: Timeslot, room: Room) -> ScheduledLesson:
    request = event.request
    return ScheduledLesson(
        request_id=request.id,
        event_id=event.id,
        teacher=request.teacher,
        semester=request.semester,
        subject=request.subject,
        activity_type=request.activity_type,
        groups=request.groups,
        source_kind=request.source_kind,
        timeslot=timeslot,
        room=room,
        estimated_students=request.estimated_students,
    )


def infeasible_result(events: list[Event], message: str) -> ScheduleResult:
    return ScheduleResult(
        lessons=[],
        issues=[
            ScheduleIssue(
                severity="error",
                code="INFEASIBLE",
                message=message,
                event_ids=tuple(event.id for event in events),
            )
        ],
        objective_value=0,
        solver_name="OR-Tools CP-SAT",
    )
