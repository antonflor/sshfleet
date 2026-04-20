from __future__ import annotations

import threading
import time


def _make_job(nda, host, *, error=None, device_type="dummy"):
    return nda.DeviceJob(
        host=host,
        username="u",
        password="p",
        commands=["show version"],
        reachable=error is None,
        device_type=device_type if error is None else None,
        error=error,
    )


def test_run_jobs_sequential_preserves_order(nda, monkeypatch):
    seen = []

    def fake_execute(job, config_mode):
        seen.append(job.host)
        return nda.DeviceResult(device=job.host, complete=True)

    monkeypatch.setattr(nda, "execute_job", fake_execute)

    jobs = [_make_job(nda, f"10.0.0.{i}") for i in range(5)]
    results = nda.run_jobs(jobs, config_mode=False, concurrency=1)

    assert [r.device for r in results] == [j.host for j in jobs]
    assert seen == [j.host for j in jobs]


def test_run_jobs_concurrent_returns_results_in_input_order(nda, monkeypatch):
    def fake_execute(job, config_mode):
        # sleep inversely to index so completion order != input order
        delay = 0.05 if job.host.endswith("0") else 0.01
        time.sleep(delay)
        return nda.DeviceResult(device=job.host, complete=True)

    monkeypatch.setattr(nda, "execute_job", fake_execute)

    jobs = [_make_job(nda, f"10.0.0.{i}") for i in range(4)]
    results = nda.run_jobs(jobs, config_mode=False, concurrency=4)
    assert [r.device for r in results] == [j.host for j in jobs]


def test_run_jobs_actually_parallelizes(nda, monkeypatch):
    active = 0
    peak = 0
    lock = threading.Lock()

    def fake_execute(job, config_mode):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return nda.DeviceResult(device=job.host, complete=True)

    monkeypatch.setattr(nda, "execute_job", fake_execute)

    jobs = [_make_job(nda, f"10.0.0.{i}") for i in range(6)]
    nda.run_jobs(jobs, config_mode=False, concurrency=4)

    assert peak >= 2, f"expected parallel execution, peak={peak}"


def test_run_jobs_rejects_zero_concurrency(nda):
    import pytest

    with pytest.raises(ValueError):
        nda.run_jobs([], config_mode=False, concurrency=0)


def test_run_jobs_empty_list(nda, monkeypatch):
    monkeypatch.setattr(
        nda, "execute_job", lambda *a, **kw: (_ for _ in ()).throw(AssertionError())
    )
    assert nda.run_jobs([], config_mode=False, concurrency=4) == []


def test_parse_args_concurrency_default_and_override(nda):
    assert nda.parse_args([]).concurrency == 1
    assert nda.parse_args(["--concurrency", "8"]).concurrency == 8


def test_parse_args_rejects_bad_concurrency(nda):
    import pytest

    with pytest.raises(SystemExit):
        nda.parse_args(["--concurrency", "0"])
