import builtins
import json
import logging
import os
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from newsreader import daemon as daemon_module


class DummyDB:
    def __init__(self, *args, **kwargs):
        self.article_count = 0
        self.updated_scores = []

    def get_article_count(self):
        return self.article_count

    def get_articles(self, limit=10000):
        return [
            {
                "id": 1,
                "title": "Sample",
                "summary": "Sample",
                "content": "Sample content",
                "source": "Default",
                "published_date": None,
            }
        ]

    def get_default_score_words(self):
        return [{"word": "sample", "weight": 1}]

    def update_article_score(self, article_id, score, user_id=None):
        self.updated_scores.append((article_id, score, user_id))


class DummyFetcher:
    def __init__(self, db, sources_file):
        self.db = db
        self.sources_file = Path(sources_file)
        self.fetch_all_sources_calls = []
        self.fetch_all_sources_result = {"skipped_existing": 0}
        self.fetch_exception = None
        self.cleanup_calls = []
        self.cleanup_result = 0
        self.cleanup_exception = None
        self.stats_result = {"default": 0}
        self.stats_exception = None
        self._type_error_emitted = False

    def fetch_all_sources(self, max_articles=None):
        self.fetch_all_sources_calls.append(max_articles)
        if self.fetch_exception == "type_error_once":
            if not self._type_error_emitted:
                self._type_error_emitted = True
                raise TypeError("type error on first call")
        elif isinstance(self.fetch_exception, Exception):
            raise self.fetch_exception
        return self.fetch_all_sources_result

    def cleanup_old_articles(self, days):
        self.cleanup_calls.append(days)
        if isinstance(self.cleanup_exception, Exception):
            raise self.cleanup_exception
        return self.cleanup_result

    def get_source_stats(self):
        if isinstance(self.stats_exception, Exception):
            raise self.stats_exception
        return self.stats_result


class DummyScorer:
    def __init__(self, db):
        self.db = db
        self.calls = 0
        self.exception = None

    def score_all_articles(self):
        self.calls += 1
        if self.exception:
            raise self.exception


class Factory:
    def __init__(self, cls):
        self.cls = cls
        self.instances = []

    def __call__(self, *args, **kwargs):
        instance = self.cls(*args, **kwargs)
        self.instances.append(instance)
        return instance


@pytest.fixture(autouse=True)
def reset_schedule():
    daemon_module.schedule.clear()
    yield
    daemon_module.schedule.clear()


@pytest.fixture
def daemon_builder(monkeypatch, tmp_path, request):
    signal_calls = {}

    def fake_signal(sig, handler):
        signal_calls[sig] = handler

    monkeypatch.setattr(daemon_module.signal, "signal", fake_signal)

    db_factory = Factory(DummyDB)
    fetcher_factory = Factory(DummyFetcher)
    scorer_factory = Factory(DummyScorer)

    monkeypatch.setattr(daemon_module, "DatabaseManager", db_factory)
    monkeypatch.setattr(daemon_module, "NewsFetcher", fetcher_factory)
    monkeypatch.setattr(daemon_module, "ArticleScorer", scorer_factory)

    def default_config():
        return {
            "fetch_interval_minutes": 15,
            "max_articles_per_source": 5,
            "cleanup_days": 7,
            "daemon_enabled": True,
            "sources": [],
        }

    def build(*, config_overrides=None, create_config=True, raw_config=None, lock_path=None):
        index = len(db_factory.instances)
        config_path = tmp_path / f"sources_{index}.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if create_config:
            if raw_config is not None:
                config_path.write_text(raw_config, encoding="utf-8")
            else:
                config = default_config()
                if config_overrides:
                    config.update(config_overrides)
                config_path.write_text(json.dumps(config), encoding="utf-8")
        else:
            if config_path.exists():
                config_path.unlink()
        chosen_lock = Path(lock_path) if lock_path else tmp_path / f"daemon_{index}.pid"
        chosen_lock.parent.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(daemon_module.NewsDaemon, "LOCKFILE", chosen_lock)
        signal_calls.clear()
        instance = daemon_module.NewsDaemon(str(config_path))
        ctx = SimpleNamespace(
            daemon=instance,
            db=db_factory.instances[-1],
            fetcher=fetcher_factory.instances[-1],
            scorer=scorer_factory.instances[-1],
            signals=dict(signal_calls),
            config_path=config_path,
            lock_path=chosen_lock,
        )

        def finalize():
            try:
                instance.cleanup()
            finally:
                if chosen_lock.exists():
                    chosen_lock.unlink()

        request.addfinalizer(finalize)
        return ctx

    return SimpleNamespace(
        build=build,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        default_config=default_config,
        signal_calls=signal_calls,
        db_factory=db_factory,
        fetcher_factory=fetcher_factory,
        scorer_factory=scorer_factory,
    )


def test_daemon_60_loads_config_values(daemon_builder):
    ctx = daemon_builder.build(
        config_overrides={
            "fetch_interval_minutes": 42,
            "max_articles_per_source": 3,
            "cleanup_days": 2,
            "daemon_enabled": True,
        }
    )
    assert ctx.daemon.config["fetch_interval_minutes"] == 42
    assert ctx.daemon.config["max_articles_per_source"] == 3
    assert ctx.daemon.config["cleanup_days"] == 2
    assert ctx.daemon.config["enabled"] is True
    assert ctx.daemon.sources_file == ctx.config_path


def test_daemon_61_handles_missing_config_file_with_defaults(daemon_builder):
    ctx = daemon_builder.build(create_config=False)
    assert ctx.daemon.config["fetch_interval_minutes"] == 30
    assert ctx.daemon.config["max_articles_per_source"] == 10
    assert ctx.daemon.config["cleanup_days"] == 30
    assert ctx.daemon.config["enabled"] is True


def test_daemon_62_handles_invalid_config_json(daemon_builder):
    ctx = daemon_builder.build(raw_config="not-valid-json")
    assert ctx.daemon.config["fetch_interval_minutes"] == 30
    assert ctx.daemon.config["max_articles_per_source"] == 10
    assert ctx.daemon.config["cleanup_days"] == 30


def test_daemon_63_registers_signal_handlers(daemon_builder):
    ctx = daemon_builder.build()
    assert signal.SIGINT in ctx.signals
    assert signal.SIGTERM in ctx.signals


def test_daemon_64_writes_lockfile_with_current_pid(daemon_builder):
    ctx = daemon_builder.build()
    assert ctx.lock_path.exists()
    assert ctx.lock_path.read_text(encoding="utf-8") == str(os.getpid())


def test_daemon_65_rejects_running_instance_via_lockfile(daemon_builder):
    config_path = daemon_builder.tmp_path / "conflict_sources.json"
    config_path.write_text(json.dumps(daemon_builder.default_config()), encoding="utf-8")
    lock_path = daemon_builder.tmp_path / "conflict.pid"
    lock_path.write_text(str(os.getpid() + 1), encoding="utf-8")
    daemon_builder.monkeypatch.setattr(daemon_module.NewsDaemon, "LOCKFILE", lock_path)
    daemon_builder.monkeypatch.setattr(daemon_module.NewsDaemon, "_pid_running", lambda self, pid: True)
    with pytest.raises(SystemExit) as exc:
        daemon_module.NewsDaemon(str(config_path))
    assert exc.value.code == 1
    lock_path.unlink(missing_ok=True)


def test_daemon_66_rejects_lockfile_with_invalid_pid(daemon_builder):
    config_path = daemon_builder.tmp_path / "invalid_sources.json"
    config_path.write_text(json.dumps(daemon_builder.default_config()), encoding="utf-8")
    lock_path = daemon_builder.tmp_path / "invalid.pid"
    lock_path.write_text("not-a-pid", encoding="utf-8")
    daemon_builder.monkeypatch.setattr(daemon_module.NewsDaemon, "LOCKFILE", lock_path)
    with pytest.raises(SystemExit) as exc:
        daemon_module.NewsDaemon(str(config_path))
    assert exc.value.code == 1
    lock_path.unlink(missing_ok=True)


def test_daemon_67_pid_running_false_for_nonpositive(daemon_builder):
    ctx = daemon_builder.build()
    assert ctx.daemon._pid_running(0) is False
    assert ctx.daemon._pid_running(-10) is False


def test_daemon_68_pid_running_uses_psutil_when_available(daemon_builder):
    fake_psutil = SimpleNamespace(pid_exists=lambda pid: pid == 321)
    daemon_builder.monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    ctx = daemon_builder.build()
    assert ctx.daemon._pid_running(321) is True
    assert ctx.daemon._pid_running(99) is False


def test_daemon_69_pid_running_fallback_uses_os_kill(daemon_builder):
    ctx = daemon_builder.build()

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("simulated missing psutil")
        return real_import(name, *args, **kwargs)

    daemon_builder.monkeypatch.setattr(builtins, "__import__", fake_import)
    daemon_builder.monkeypatch.setattr(daemon_module.os, "name", "posix", raising=False)
    calls = []

    def fake_kill(pid, sig):
        calls.append((pid, sig))
        if pid == 999:
            raise OSError

    daemon_builder.monkeypatch.setattr(daemon_module.os, "kill", fake_kill, raising=False)
    assert ctx.daemon._pid_running(888) is True
    assert ctx.daemon._pid_running(999) is False
    assert calls[0] == (888, 0)


def test_daemon_70_signal_handler_stops_daemon_and_releases_lock(daemon_builder):
    ctx = daemon_builder.build()
    ctx.daemon.running = True
    released = []
    ctx.daemon._release_lock = lambda: released.append(True)
    ctx.daemon.signal_handler(signal.SIGINT, None)
    assert ctx.daemon.running is False
    assert released == [True]


def test_daemon_71_fetch_news_job_uses_configured_limits(daemon_builder, caplog):
    ctx = daemon_builder.build(config_overrides={"max_articles_per_source": 7})
    ctx.db.article_count = 5
    ctx.fetcher.fetch_all_sources_result = {"skipped_existing": 2}
    with caplog.at_level(logging.INFO, logger="newsreader.daemon"):
        ctx.daemon.fetch_news_job()
    assert ctx.fetcher.fetch_all_sources_calls == [7]
    assert ctx.scorer.calls == 1
    assert any("Articles in DB before fetch: 5" in message for message in caplog.messages)


def test_daemon_72_fetch_news_job_logs_when_skip_count_missing(daemon_builder, caplog):
    ctx = daemon_builder.build()
    ctx.fetcher.fetch_all_sources_result = {"other": 1}
    with caplog.at_level(logging.INFO, logger="newsreader.daemon"):
        ctx.daemon.fetch_news_job()
    assert any("count not available" in message for message in caplog.messages)


def test_daemon_73_fetch_news_job_handles_missing_method(daemon_builder, caplog):
    ctx = daemon_builder.build()
    original_fetcher = ctx.daemon.fetcher
    ctx.daemon.fetcher = SimpleNamespace()
    with caplog.at_level(logging.INFO, logger="newsreader.daemon"):
        ctx.daemon.fetch_news_job()
    assert any("does not support fetch_all_sources" in message for message in caplog.messages)
    ctx.daemon.fetcher = original_fetcher


def test_daemon_74_fetch_news_job_handles_type_error_retry(daemon_builder, caplog):
    ctx = daemon_builder.build()
    ctx.fetcher.fetch_exception = "type_error_once"
    with caplog.at_level(logging.INFO, logger="newsreader.daemon"):
        ctx.daemon.fetch_news_job()
    expected = ctx.daemon.config["max_articles_per_source"]
    assert ctx.fetcher.fetch_all_sources_calls == [expected, expected]
    assert any("count not available" in message for message in caplog.messages)


def test_daemon_75_fetch_news_job_logs_and_suppresses_exceptions(daemon_builder, caplog):
    ctx = daemon_builder.build()
    ctx.fetcher.fetch_exception = RuntimeError("boom")
    with caplog.at_level(logging.ERROR, logger="newsreader.daemon"):
        ctx.daemon.fetch_news_job()
    assert ctx.scorer.calls == 0
    assert any("Error in news fetch job" in message for message in caplog.messages)


def test_daemon_76_cleanup_job_calls_fetcher_with_days(daemon_builder):
    ctx = daemon_builder.build(config_overrides={"cleanup_days": 11})
    ctx.fetcher.cleanup_result = 9
    ctx.daemon.cleanup_job()
    assert ctx.fetcher.cleanup_calls == [11]


def test_daemon_77_cleanup_job_logs_and_suppresses_exceptions(daemon_builder, caplog):
    ctx = daemon_builder.build()
    ctx.fetcher.cleanup_exception = RuntimeError("cleanup-fail")
    with caplog.at_level(logging.ERROR, logger="newsreader.daemon"):
        ctx.daemon.cleanup_job()
    assert any("Error in cleanup job" in message for message in caplog.messages)


def test_daemon_78_stats_job_logs_counts(daemon_builder, caplog):
    ctx = daemon_builder.build()
    ctx.db.article_count = 4
    ctx.fetcher.stats_result = {"Source": 2}
    with caplog.at_level(logging.INFO, logger="newsreader.daemon"):
        ctx.daemon.stats_job()
    assert any("System stats: 4 total articles" in message for message in caplog.messages)
    assert any("Source" in message for message in caplog.messages)


def test_daemon_79_stats_job_logs_on_exception(daemon_builder, caplog):
    ctx = daemon_builder.build()
    ctx.fetcher.stats_exception = RuntimeError("stats")
    with caplog.at_level(logging.ERROR, logger="newsreader.daemon"):
        ctx.daemon.stats_job()
    assert any("Error in stats job" in message for message in caplog.messages)


def test_daemon_80_setup_schedule_adds_expected_jobs(daemon_builder):
    ctx = daemon_builder.build(config_overrides={"fetch_interval_minutes": 21})
    daemon_module.schedule.clear()
    ctx.daemon.setup_schedule()
    jobs = daemon_module.schedule.get_jobs()
    assert len(jobs) == 3
    units = {job.unit for job in jobs}
    assert units == {"minutes", "days", "hours"}
    minute_job = next(job for job in jobs if job.unit == "minutes")
    assert minute_job.interval == 21
    day_job = next(job for job in jobs if job.unit == "days")
    assert day_job.at_time.strftime("%H:%M") == "02:00"


def test_daemon_81_run_once_invokes_all_jobs(daemon_builder):
    ctx = daemon_builder.build()
    ctx.fetcher.cleanup_result = 5
    ctx.fetcher.stats_result = {"A": 1}
    ctx.daemon.run_once()
    expected = ctx.daemon.config["max_articles_per_source"]
    assert ctx.fetcher.fetch_all_sources_calls == [expected]
    expected_cleanup = ctx.daemon.config["cleanup_days"]
    assert ctx.fetcher.cleanup_calls == [expected_cleanup]
    assert ctx.scorer.calls == 1


def test_daemon_82_run_skips_when_disabled(daemon_builder):
    ctx = daemon_builder.build(config_overrides={"daemon_enabled": False})
    ctx.daemon.run()
    assert ctx.fetcher.fetch_all_sources_calls == []
    assert ctx.scorer.calls == 0


def test_daemon_83_run_executes_loop_and_respects_running_flag(daemon_builder):
    ctx = daemon_builder.build()
    runs = []

    def fake_run_pending():
        runs.append(True)
        ctx.daemon.running = False

    sleeps = []
    daemon_builder.monkeypatch.setattr(daemon_module.schedule, "run_pending", fake_run_pending)
    daemon_builder.monkeypatch.setattr(daemon_module.time, "sleep", lambda seconds: sleeps.append(seconds))
    ctx.daemon.run()
    expected = ctx.daemon.config["max_articles_per_source"]
    assert ctx.fetcher.fetch_all_sources_calls == [expected]
    assert runs == [True]
    assert sleeps == [60]


def test_daemon_84_run_invokes_setup_schedule_once(daemon_builder):
    ctx = daemon_builder.build()
    original_setup = ctx.daemon.setup_schedule
    calls = []

    def tracking_setup():
        calls.append(True)
        original_setup()

    ctx.daemon.setup_schedule = tracking_setup
    daemon_builder.monkeypatch.setattr(daemon_module.schedule, "run_pending", lambda: setattr(ctx.daemon, "running", False))
    daemon_builder.monkeypatch.setattr(daemon_module.time, "sleep", lambda _: None)
    ctx.daemon.run()
    assert calls == [True]


def test_daemon_85_run_handles_keyboard_interrupt_and_cleans_up(daemon_builder, caplog):
    ctx = daemon_builder.build()
    daemon_builder.monkeypatch.setattr(
        daemon_module.schedule,
        "run_pending",
        lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    daemon_builder.monkeypatch.setattr(daemon_module.time, "sleep", lambda _: None)
    released = []
    ctx.daemon._release_lock = lambda: released.append(True)
    with caplog.at_level(logging.INFO, logger="newsreader.daemon"):
        ctx.daemon.run()
    messages = "\n".join(caplog.messages)
    assert "Daemon stopped by user" in messages
    assert "Daemon shutting down" in messages
    assert released == [True]


def test_daemon_86_run_handles_unexpected_exception_and_cleans_up(daemon_builder, caplog):
    ctx = daemon_builder.build()
    daemon_builder.monkeypatch.setattr(
        daemon_module.schedule,
        "run_pending",
        lambda: (_ for _ in ()).throw(RuntimeError("loop")),
    )
    daemon_builder.monkeypatch.setattr(daemon_module.time, "sleep", lambda _: None)
    released = []
    ctx.daemon._release_lock = lambda: released.append(True)
    with caplog.at_level(logging.ERROR, logger="newsreader.daemon"):
        ctx.daemon.run()
    assert any("Unexpected error in daemon" in message for message in caplog.messages)
    assert released == [True]


def test_daemon_87_cleanup_removes_lockfile(daemon_builder):
    ctx = daemon_builder.build()
    assert ctx.lock_path.exists()
    ctx.daemon.cleanup()
    assert ctx.lock_path.exists() is False


def test_daemon_88_cleanup_handles_missing_lockfile(daemon_builder):
    ctx = daemon_builder.build()
    ctx.lock_path.unlink()
    ctx.daemon.cleanup()
    assert ctx.lock_path.exists() is False


def test_daemon_89_release_lock_ignores_missing_file(daemon_builder):
    ctx = daemon_builder.build()
    ctx.lock_path.unlink()
    ctx.daemon._release_lock()
    assert ctx.lock_path.exists() is False


def test_daemon_90_main_runs_once_with_flag(daemon_builder):
    instances = []

    class FakeDaemon:
        def __init__(self, config_path):
            self.config_path = config_path
            self.run_called = False
            self.run_once_called = False
            instances.append(self)

        def run(self):
            self.run_called = True

        def run_once(self):
            self.run_once_called = True

    daemon_builder.monkeypatch.setattr(daemon_module, "NewsDaemon", FakeDaemon)
    daemon_builder.monkeypatch.setattr(sys, "argv", ["daemon", "--once"])
    daemon_module.main()
    assert instances[-1].run_once_called is True
    assert instances[-1].run_called is False


def test_daemon_91_main_runs_daemon_without_flags(daemon_builder):
    instances = []

    class FakeDaemon:
        def __init__(self, config_path):
            self.config_path = config_path
            self.run_called = False
            self.run_once_called = False
            instances.append(self)

        def run(self):
            self.run_called = True

        def run_once(self):
            self.run_once_called = True

    daemon_builder.monkeypatch.setattr(daemon_module, "NewsDaemon", FakeDaemon)
    daemon_builder.monkeypatch.setattr(sys, "argv", ["daemon"])
    daemon_module.main()
    assert instances[-1].run_called is True
    assert instances[-1].run_once_called is False


def test_daemon_92_main_passes_config_path_argument(daemon_builder):
    instances = []

    class FakeDaemon:
        def __init__(self, config_path):
            self.config_path = config_path
            self.run_called = False
            self.run_once_called = False
            instances.append(self)

        def run(self):
            self.run_called = True

        def run_once(self):
            self.run_once_called = True

    custom_config = str(daemon_builder.tmp_path / "custom.json")
    daemon_builder.monkeypatch.setattr(daemon_module, "NewsDaemon", FakeDaemon)
    daemon_builder.monkeypatch.setattr(sys, "argv", ["daemon", "--config", custom_config, "--once"])
    daemon_module.main()
    assert Path(instances[-1].config_path) == Path(custom_config)
    assert instances[-1].run_once_called is True
