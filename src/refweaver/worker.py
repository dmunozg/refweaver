"""RQ worker entrypoint."""

from __future__ import annotations

from rq import Worker

from refweaver.queue import get_queue


def main() -> None:
    queue = get_queue()
    worker = Worker([queue], connection=queue.connection)
    worker.work()


if __name__ == "__main__":
    main()
