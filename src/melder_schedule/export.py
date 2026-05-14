from __future__ import annotations

from pathlib import Path

import pandas as pd

from melder_schedule.models import ScheduleIssue, ScheduledLesson


def lessons_to_dataframe(lessons: list[ScheduledLesson]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Преподаватель": lesson.teacher,
                "Семестр": lesson.semester,
                "День": lesson.timeslot.day,
                "Пара": lesson.timeslot.pair,
                "Неделя": lesson.timeslot.week_type,
                "Дисциплина": lesson.subject,
                "Тип занятия": lesson.activity_type.value,
                "Группы": ", ".join(lesson.groups),
                "Аудитория": lesson.room.name,
                "Вместимость": lesson.room.capacity,
                "Студентов": lesson.estimated_students,
                "ID занятия": lesson.event_id,
            }
            for lesson in lessons
        ]
    )


def issues_to_dataframe(issues: list[ScheduleIssue]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Важность": issue.severity,
                "Код": issue.code,
                "Описание": issue.message,
                "Занятия": ", ".join(issue.event_ids),
            }
            for issue in issues
        ]
    )


def export_schedule_excel(
    lessons: list[ScheduledLesson],
    issues: list[ScheduleIssue],
    path: str | Path,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        lessons_to_dataframe(lessons).to_excel(writer, sheet_name="Расписание", index=False)
        issues_to_dataframe(issues).to_excel(writer, sheet_name="Проверка", index=False)
    return output_path
