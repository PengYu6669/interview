import asyncio

from interview_copilot.api.questions import run_question_job_worker


def main() -> None:
    stop = asyncio.Event()
    try:
        asyncio.run(run_question_job_worker(stop))
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
