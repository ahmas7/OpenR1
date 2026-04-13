"""
Tests for R1 Jobs System
"""
import asyncio
import json
import pytest
from datetime import datetime, timedelta

from R1.config.settings import settings
from R1.jobs.manager import JobManager, JobDefinition, CronExpr
from R1.jobs.reminders import ReminderQueue, Reminder, get_reminder_queue


# ==================== Cron Expression Tests ====================

class TestCronExpr:
    def test_every_minute(self):
        cron = CronExpr("* * * * *")
        # Should match any datetime
        dt = datetime(2024, 6, 15, 10, 30, 0)
        assert cron.matches(dt)

    def test_specific_minute(self):
        cron = CronExpr("30 * * * *")
        assert cron.matches(datetime(2024, 6, 15, 10, 30, 0))
        assert not cron.matches(datetime(2024, 6, 15, 10, 31, 0))

    def test_specific_hour_minute(self):
        cron = CronExpr("0 9 * * *")
        assert cron.matches(datetime(2024, 6, 15, 9, 0, 0))
        assert not cron.matches(datetime(2024, 6, 15, 10, 0, 0))

    def test_range(self):
        cron = CronExpr("0-5 * * * *")
        assert cron.matches(datetime(2024, 6, 15, 10, 3, 0))
        assert not cron.matches(datetime(2024, 6, 15, 10, 10, 0))

    def test_step(self):
        cron = CronExpr("*/15 * * * *")
        assert cron.matches(datetime(2024, 6, 15, 10, 0, 0))
        assert cron.matches(datetime(2024, 6, 15, 10, 15, 0))
        assert cron.matches(datetime(2024, 6, 15, 10, 30, 0))
        assert not cron.matches(datetime(2024, 6, 15, 10, 7, 0))

    def test_comma_list(self):
        cron = CronExpr("0,30 * * * *")
        assert cron.matches(datetime(2024, 6, 15, 10, 0, 0))
        assert cron.matches(datetime(2024, 6, 15, 10, 30, 0))
        assert not cron.matches(datetime(2024, 6, 15, 10, 15, 0))

    def test_invalid_expression(self):
        with pytest.raises(ValueError):
            CronExpr("* *")  # Too few fields

    def test_weekday(self):
        # 2024-06-17 is a Monday (weekday=0 in Python, cron weekday=1)
        cron = CronExpr("* * * * 1")  # Monday in cron
        assert cron.matches(datetime(2024, 6, 17, 10, 0, 0))

    def test_repr(self):
        cron = CronExpr("*/5 * * * *")
        assert "*/5" in repr(cron)


# ==================== Job Manager Tests ====================

class TestJobManager:
    @pytest.fixture
    def manager(self):
        settings.jobs_enabled = True
        return JobManager()

    def test_register_and_list(self, manager):
        async def handler(services):
            pass

        job = JobDefinition(id="test1", name="Test Job", interval_seconds=60, handler=handler)
        manager.register_job(job)

        jobs = manager.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "test1"

    def test_get_job_status(self, manager):
        async def handler(services):
            pass

        job = JobDefinition(id="test2", name="Test Job 2", interval_seconds=30, handler=handler)
        manager.register_job(job)

        status = manager.get_job_status("test2")
        assert status is not None
        assert status["id"] == "test2"
        assert status["enabled"] is True
        assert status["run_count"] == 0

    def test_get_job_status_not_found(self, manager):
        assert manager.get_job_status("nonexistent") is None

    def test_enable_disable(self, manager):
        async def handler(services):
            pass

        job = JobDefinition(id="test3", name="Test Job 3", interval_seconds=60, handler=handler)
        manager.register_job(job)

        assert manager.disable_job("test3")
        assert not manager._jobs["test3"].enabled

        assert manager.enable_job("test3")
        assert manager._jobs["test3"].enabled

    def test_disable_nonexistent(self, manager):
        assert not manager.disable_job("nonexistent")

    def test_unregister(self, manager):
        async def handler(services):
            pass

        job = JobDefinition(id="test4", name="Test Job 4", interval_seconds=60, handler=handler)
        manager.register_job(job)
        assert len(manager.list_jobs()) == 1

        assert manager.unregister_job("test4")
        assert len(manager.list_jobs()) == 0

    def test_summary(self, manager):
        async def handler(services):
            pass

        manager.register_job(JobDefinition(id="a", name="A", interval_seconds=60, handler=handler))
        manager.register_job(JobDefinition(
            id="b", name="B", interval_seconds=60, handler=handler, enabled=False
        ))

        summary = manager.summary()
        assert summary["total_jobs"] == 2
        assert summary["active_jobs"] == 1

    def test_run_job_now(self, manager):
        call_count = 0

        async def handler(services):
            nonlocal call_count
            call_count += 1

        job = JobDefinition(id="test5", name="Test Job 5", interval_seconds=3600, handler=handler)
        manager.register_job(job)

        result = asyncio.run(manager.run_job_now("test5"))
        assert result is True
        assert call_count == 1
        assert manager._jobs["test5"].run_count == 1

    def test_to_dict(self, manager):
        async def handler(services):
            pass

        job = JobDefinition(id="test6", name="Test Job 6", interval_seconds=60, handler=handler)
        d = job.to_dict()
        assert d["id"] == "test6"
        assert d["name"] == "Test Job 6"
        assert d["interval_seconds"] == 60
        assert d["cron_expr"] is None


# ==================== Reminder Tests ====================

class TestReminderQueue:
    @pytest.fixture
    def queue(self, tmp_path):
        return ReminderQueue(str(tmp_path / "test_reminders.json"))

    def test_add_reminder(self, queue):
        r = queue.add("session1", "Buy milk", "2099-12-31T00:00:00")
        assert r.id
        assert r.text == "Buy milk"
        assert r.session_id == "session1"
        assert not r.delivered

    def test_list_pending(self, queue):
        queue.add("s1", "Task 1", "2099-12-31T00:00:00")
        queue.add("s1", "Task 2", "2099-12-31T00:00:00")

        pending = queue.list_pending()
        assert len(pending) == 2

    def test_cancel_reminder(self, queue):
        r = queue.add("s1", "Cancel me", "2099-12-31T00:00:00")
        assert queue.cancel(r.id)
        assert queue.pending_count() == 0

    def test_cancel_nonexistent(self, queue):
        assert not queue.cancel("nonexistent")

    def test_deliver_due(self, queue):
        # Create a reminder that's already due
        past = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        queue.add("s1", "Due now", past)

        delivered = queue.deliver_due()
        assert len(delivered) == 1
        assert delivered[0].text == "Due now"
        assert delivered[0].delivered

        # Should not deliver again
        delivered2 = queue.deliver_due()
        assert len(delivered2) == 0

    def test_future_reminder_not_delivered(self, queue):
        future = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        queue.add("s1", "Not yet", future)

        delivered = queue.deliver_due()
        assert len(delivered) == 0
        assert queue.pending_count() == 1

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "persist_test.json")

        # Write
        q1 = ReminderQueue(path)
        q1.add("s1", "Persistent", "2099-12-31T00:00:00")

        # Read back
        q2 = ReminderQueue(path)
        assert q2.pending_count() == 1
        assert q2.list_pending()[0].text == "Persistent"

    def test_get_reminder(self, queue):
        r = queue.add("s1", "Find me", "2099-12-31T00:00:00")
        found = queue.get(r.id)
        assert found is not None
        assert found.text == "Find me"

        assert queue.get("nonexistent") is None

    def test_is_due(self):
        past = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        r_past = Reminder(id="1", session_id="s", text="t", due_at=past, created_at="now")
        r_future = Reminder(id="2", session_id="s", text="t", due_at=future, created_at="now")
        r_delivered = Reminder(id="3", session_id="s", text="t", due_at=past, created_at="now", delivered=True)

        assert r_past.is_due()
        assert not r_future.is_due()
        assert not r_delivered.is_due()
