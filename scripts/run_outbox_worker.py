from __future__ import annotations

import argparse
import asyncio
import signal

from reservas_api.infrastructure.outbox import OutboxEventProcessor
from reservas_api.shared.config import ApplicationContainer, settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run outbox event worker.")
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=2.0,
        help="Polling interval for pending outbox events.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Maximum events processed per poll cycle.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one batch and exit.",
    )
    return parser.parse_args()


async def _run_worker(args: argparse.Namespace) -> None:
    container = ApplicationContainer(settings)
    await container.startup()
    try:
        processor = OutboxEventProcessor(
            session_factory=container.session_factory,
            payment_gateway=container.create_payment_gateway(),
            provider_gateway=container.create_provider_gateway(),
            poll_interval_seconds=args.poll_interval_seconds,
            batch_size=args.batch_size,
        )

        if args.once:
            processed = await processor.process_pending_once(limit=args.batch_size)
            print(f"Processed events: {processed}")
            return

        stop_event = asyncio.Event()

        def _request_stop() -> None:
            processor.stop()
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _request_stop)
            except NotImplementedError:
                pass

        worker_task = asyncio.create_task(processor.run_forever())
        await stop_event.wait()
        await worker_task
    finally:
        await container.shutdown()


def main() -> int:
    args = parse_args()
    try:
        asyncio.run(_run_worker(args))
        return 0
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
