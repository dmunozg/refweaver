from pytest import MonkeyPatch

from refweaver.worker import main


def test_worker_validates_identity_config_on_startup(monkeypatch: MonkeyPatch) -> None:
    class DummyQueue:
        connection = object()

    class DummyWorker:
        def __init__(self, queues: list[object], connection: object) -> None:
            self.queues = queues
            self.connection = connection

        def work(self) -> None:
            return None

    called = {"validate": 0}

    def fake_validate() -> None:
        called["validate"] += 1

    monkeypatch.setattr("refweaver.worker.get_queue", lambda: DummyQueue())
    monkeypatch.setattr("refweaver.worker.Worker", DummyWorker)
    monkeypatch.setattr("refweaver.worker.validate_http_identity_config", fake_validate)

    main()

    assert called["validate"] == 1
