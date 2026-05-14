from pathlib import Path

from melder_schedule.demo_data import default_rooms, default_timeslots
from melder_schedule.optimizer import optimize_schedule
from melder_schedule.parser import parse_workload_excel
from melder_schedule.validator import validate_schedule


BASE_DIR = Path(__file__).resolve().parents[1]


def test_optimizer_builds_conflict_free_demo_schedule() -> None:
    requests = parse_workload_excel(BASE_DIR / "Нагрузка 2025-2026.xlsx")[:25]

    result = optimize_schedule(requests, default_rooms(), default_timeslots())
    issues = [*result.issues, *validate_schedule(result.lessons)]

    assert result.lessons
    assert not [issue for issue in issues if issue.severity == "error"]
