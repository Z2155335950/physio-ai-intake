from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.memory.base import VisitCompletionError
from app.memory.models import (
    CustomerCreate,
    ScheduleWindow,
    SlotAppointmentCreate,
)
from app.memory.sqlite_store import SqliteCustomerMemoryStore


class AppointmentScheduleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteCustomerMemoryStore(
            Path(self.temp_dir.name) / "schedule.sqlite3"
        )
        self.customer = asyncio.run(
            self.store.create_customer(
                CustomerCreate(name="排班客户", phone="13800006666")
            )
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_generate_select_close_and_reopen_slots(self) -> None:
        target = date(2026, 11, 16)
        schedule = asyncio.run(
            self.store.configure_day_schedule(
                ScheduleWindow(
                    schedule_date=target,
                    start_time="09:00",
                    end_time="11:00",
                    interval_minutes=30,
                )
            )
        )
        self.assertEqual(len(schedule.slots), 4)
        first = schedule.slots[0]
        closed = asyncio.run(
            self.store.update_slot_status(first.id, "closed")
        )
        self.assertEqual(closed.status, "closed")
        reopened = asyncio.run(
            self.store.update_slot_status(first.id, "available")
        )
        self.assertEqual(reopened.status, "available")

        appointment = asyncio.run(
            self.store.schedule_customer_slot(
                self.customer.id,
                SlotAppointmentCreate(
                    slot_id=first.id,
                    service_item="腰部调理",
                    note="请提前十分钟到店",
                ),
            )
        )
        self.assertEqual(appointment.slot_id, first.id)
        refreshed = asyncio.run(self.store.get_day_schedule(target))
        booked = next(slot for slot in refreshed.slots if slot.id == first.id)
        self.assertEqual(booked.status, "booked")
        self.assertEqual(booked.customer_name, "排班客户")
        self.assertEqual(booked.customer_id, self.customer.id)
        self.assertEqual(booked.appointment_id, appointment.id)
        self.assertEqual(booked.service_item, "腰部调理")
        self.assertEqual(booked.note, "请提前十分钟到店")

        with self.assertRaises(VisitCompletionError) as duplicate:
            asyncio.run(
                self.store.schedule_customer_slot(
                    self.customer.id,
                    SlotAppointmentCreate(slot_id=first.id),
                )
            )
        self.assertEqual(duplicate.exception.code, "slot_unavailable")
        with self.assertRaises(VisitCompletionError) as close_booked:
            asyncio.run(
                self.store.update_slot_status(first.id, "closed")
            )
        self.assertEqual(close_booked.exception.code, "slot_booked")

    def test_reconfigure_day_preserves_booked_appointment(self) -> None:
        target = date(2026, 11, 17)
        schedule = asyncio.run(
            self.store.configure_day_schedule(
                ScheduleWindow(
                    schedule_date=target,
                    start_time="09:00",
                    end_time="11:00",
                    interval_minutes=60,
                )
            )
        )
        booked_slot = schedule.slots[0]
        asyncio.run(
            self.store.schedule_customer_slot(
                self.customer.id,
                SlotAppointmentCreate(slot_id=booked_slot.id),
            )
        )
        updated = asyncio.run(
            self.store.configure_day_schedule(
                ScheduleWindow(
                    schedule_date=target,
                    start_time="10:00",
                    end_time="12:00",
                    interval_minutes=60,
                )
            )
        )
        self.assertTrue(any(slot.id == booked_slot.id for slot in updated.slots))
        self.assertTrue(
            any(slot.start_at.hour == 10 and slot.status == "available" for slot in updated.slots)
        )

    def test_cancel_releases_slot_and_complete_locks_it(self) -> None:
        target = date(2026, 11, 18)
        schedule = asyncio.run(
            self.store.configure_day_schedule(
                ScheduleWindow(
                    schedule_date=target,
                    start_time="09:00",
                    end_time="10:00",
                    interval_minutes=60,
                )
            )
        )
        slot = schedule.slots[0]
        appointment = asyncio.run(
            self.store.schedule_customer_slot(
                self.customer.id,
                SlotAppointmentCreate(slot_id=slot.id),
            )
        )
        cancelled = asyncio.run(
            self.store.update_appointment_status(
                self.customer.id, appointment.id, "cancelled"
            )
        )
        self.assertEqual(cancelled.status, "cancelled")
        reopened = asyncio.run(self.store.get_day_schedule(target))
        self.assertEqual(reopened.slots[0].status, "available")

        second = asyncio.run(
            self.store.schedule_customer_slot(
                self.customer.id,
                SlotAppointmentCreate(slot_id=slot.id),
            )
        )
        completed = asyncio.run(
            self.store.update_appointment_status(
                self.customer.id, second.id, "completed"
            )
        )
        self.assertEqual(completed.status, "completed")
        final_schedule = asyncio.run(self.store.get_day_schedule(target))
        self.assertEqual(final_schedule.slots[0].status, "completed")
        self.assertEqual(final_schedule.slots[0].customer_id, self.customer.id)
        self.assertEqual(final_schedule.slots[0].customer_name, "排班客户")
        with self.assertRaises(VisitCompletionError):
            asyncio.run(
                self.store.schedule_customer_slot(
                    self.customer.id,
                    SlotAppointmentCreate(slot_id=slot.id),
                )
            )

    def test_assign_different_customers_to_different_time_slots(self) -> None:
        second_customer = asyncio.run(
            self.store.create_customer(
                CustomerCreate(name="第二位客户", phone="13800007777")
            )
        )
        target = date(2026, 11, 19)
        schedule = asyncio.run(
            self.store.configure_day_schedule(
                ScheduleWindow(
                    schedule_date=target,
                    start_time="09:00",
                    end_time="11:00",
                    interval_minutes=60,
                )
            )
        )
        first, second = schedule.slots
        asyncio.run(
            self.store.schedule_customer_slot(
                self.customer.id,
                SlotAppointmentCreate(
                    slot_id=first.id, service_item="腰部调理"
                ),
            )
        )
        asyncio.run(
            self.store.schedule_customer_slot(
                second_customer.id,
                SlotAppointmentCreate(
                    slot_id=second.id, service_item="肩颈调理"
                ),
            )
        )
        refreshed = asyncio.run(self.store.get_day_schedule(target))
        names_by_start = {
            slot.start_at.hour: slot.customer_name for slot in refreshed.slots
        }
        self.assertEqual(names_by_start[9], "排班客户")
        self.assertEqual(names_by_start[10], "第二位客户")


if __name__ == "__main__":
    unittest.main()
