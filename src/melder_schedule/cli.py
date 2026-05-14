from __future__ import annotations

import argparse
from pathlib import Path

from melder_schedule.demo_data import default_rooms, default_timeslots
from melder_schedule.export import export_schedule_excel, lessons_to_dataframe
from melder_schedule.optimizer import optimize_schedule
from melder_schedule.parser import parse_workload_excel
from melder_schedule.validator import quality_metrics, validate_schedule


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a teacher timetable from workload Excel data."
    )
    parser.add_argument("workload", help="Path to workload .xlsx file")
    parser.add_argument(
        "--limit",
        type=int,
        default=60,
        help="Limit lesson requests for a compact demonstrational run",
    )
    parser.add_argument(
        "--teacher",
        default="",
        help="Case-insensitive teacher name fragment",
    )
    parser.add_argument(
        "--output",
        default="data/output/schedule.xlsx",
        help="Output Excel path",
    )
    args = parser.parse_args()

    requests = parse_workload_excel(args.workload)
    if args.teacher:
        teacher_filter = args.teacher.lower()
        requests = [request for request in requests if teacher_filter in request.teacher.lower()]
    if args.limit:
        requests = requests[: args.limit]

    result = optimize_schedule(requests, default_rooms(), default_timeslots())
    issues = [*result.issues, *validate_schedule(result.lessons)]
    output = export_schedule_excel(result.lessons, issues, args.output)
    metrics = quality_metrics(result.lessons)

    print(f"Заявок: {len(requests)}")
    print(f"Занятий в расписании: {len(result.lessons)}")
    print(f"Решатель: {result.solver_name}")
    print(f"Штраф: {result.objective_value}")
    print(f"Ошибок проверки: {len([issue for issue in issues if issue.severity == 'error'])}")
    print(f"Окна преподавателей: {int(metrics['teacher_windows'])}")
    print(f"Файл результата: {Path(output).resolve()}")

    preview = lessons_to_dataframe(result.lessons).head(10)
    if not preview.empty:
        print("\nПервые строки расписания:")
        print(preview.to_string(index=False))


if __name__ == "__main__":
    main()
