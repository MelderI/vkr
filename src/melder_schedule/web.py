from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from flask import Flask, jsonify, request, send_from_directory

from melder_schedule.demo_data import default_rooms, default_timeslots
from melder_schedule.optimizer import optimize_schedule
from melder_schedule.parser import parse_workload_excel
from melder_schedule.validator import quality_metrics, validate_schedule


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
SAMPLE_FILES = [
    "Нагрузка 2023-24.xlsx",
    "нагрузка 2024-25ф.xlsx",
    "Нагрузка 2025-2026.xlsx",
]

app = Flask(__name__, static_folder=None)


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:path>")
def static_files(path: str):
    return send_from_directory(FRONTEND_DIR, path)


@app.get("/api/samples")
def samples():
    existing = [name for name in SAMPLE_FILES if (PROJECT_ROOT / name).exists()]
    return jsonify({"files": existing})


@app.post("/api/schedule")
def schedule():
    limit = parse_int(request.form.get("limit"), default=50)
    teacher = (request.form.get("teacher") or "").strip().lower()
    sample_file = (request.form.get("sample_file") or "").strip()

    try:
        workload_path = resolve_workload_file(sample_file)
        uploaded_file = request.files.get("file")
        if uploaded_file and uploaded_file.filename:
            with NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
                uploaded_file.save(temp_file.name)
                workload_path = Path(temp_file.name)

        if workload_path is None:
            return jsonify({"error": "Выберите файл нагрузки или загрузите .xlsx"}), 400

        requests = parse_workload_excel(workload_path)
        if teacher:
            requests = [item for item in requests if teacher in item.teacher.lower()]
        requests = requests[:limit]

        result = optimize_schedule(requests, default_rooms(), default_timeslots())
        issues = [*result.issues, *validate_schedule(result.lessons)]
        metrics = quality_metrics(result.lessons)

        return jsonify(
            {
                "source": uploaded_file.filename if uploaded_file and uploaded_file.filename else sample_file,
                "request_count": len(requests),
                "lesson_count": len(result.lessons),
                "solver": result.solver_name,
                "objective": result.objective_value,
                "metrics": metrics,
                "issues": [serialize_issue(issue) for issue in issues],
                "lessons": [serialize_lesson(lesson) for lesson in result.lessons],
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def resolve_workload_file(sample_file: str) -> Path | None:
    if not sample_file:
        return None
    if sample_file not in SAMPLE_FILES:
        raise ValueError("Неизвестный демонстрационный файл")
    path = PROJECT_ROOT / sample_file
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {sample_file}")
    return path


def parse_int(value: str | None, *, default: int) -> int:
    try:
        parsed = int(value or default)
    except ValueError:
        return default
    return max(1, min(parsed, 200))


def serialize_lesson(lesson) -> dict[str, object]:
    return {
        "teacher": lesson.teacher,
        "semester": lesson.semester,
        "day": lesson.timeslot.day,
        "pair": lesson.timeslot.pair,
        "week": lesson.timeslot.week_type,
        "subject": lesson.subject,
        "activity_type": lesson.activity_type.value,
        "groups": ", ".join(lesson.groups),
        "room": lesson.room.name,
        "capacity": lesson.room.capacity,
        "students": lesson.estimated_students,
        "event_id": lesson.event_id,
    }


def serialize_issue(issue) -> dict[str, object]:
    return {
        "severity": issue.severity,
        "code": issue.code,
        "message": issue.message,
        "event_ids": ", ".join(issue.event_ids),
    }


def main() -> None:
    app.run(host="127.0.0.1", port=8000, debug=True)


if __name__ == "__main__":
    main()
