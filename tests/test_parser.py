from pathlib import Path

from melder_schedule.parser import parse_workload_excel


BASE_DIR = Path(__file__).resolve().parents[1]


def test_parse_2025_workload_extracts_requests() -> None:
    requests = parse_workload_excel(BASE_DIR / "Нагрузка 2025-2026.xlsx")

    assert requests
    assert requests[0].teacher
    assert requests[0].subject
    assert requests[0].groups
    assert requests[0].required_slots >= 1


def test_parse_all_workload_files() -> None:
    files = [
        "Нагрузка 2023-24.xlsx",
        "нагрузка 2024-25ф.xlsx",
        "Нагрузка 2025-2026.xlsx",
    ]

    counts = [len(parse_workload_excel(BASE_DIR / file_name)) for file_name in files]

    assert all(count > 100 for count in counts)
