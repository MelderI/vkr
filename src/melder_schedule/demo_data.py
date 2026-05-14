from __future__ import annotations

from melder_schedule.models import Room, Timeslot


def default_rooms() -> list[Room]:
    return [
        Room(id="A101", name="101", room_type="classroom", capacity=30),
        Room(id="A102", name="102", room_type="classroom", capacity=35),
        Room(id="A201", name="201", room_type="classroom", capacity=45),
        Room(id="A301", name="301 большая аудитория", room_type="classroom", capacity=180),
        Room(id="L301", name="301 лекционная", room_type="lecture", capacity=90),
        Room(id="L302", name="302 лекционная", room_type="lecture", capacity=120),
        Room(id="C401", name="401 компьютерный класс", room_type="classroom", capacity=28),
    ]


def default_timeslots() -> list[Timeslot]:
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
    return [
        Timeslot(id=f"{day[:2]}-{pair}", day=day, pair=pair)
        for day in days
        for pair in range(1, 7)
    ]
