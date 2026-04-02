#!/usr/bin/env python
"""Script to evaluate user queries from a CSV file."""

import argparse
import asyncio
import contextlib
import json
import logging
import random
import statistics
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from tqdm.asyncio import tqdm as atqdm

from agents.agent_runner import AgentRunner
from agents.restrictor import create_restrictor_agent
from core.config import load_config
from core.logger import setup_logger
from data_processing.image_processor import process_image

logger = logging.getLogger(__name__)


def check_positive_int(value: str) -> int:
    """Checks if the value is a positive integer.

    Args:
        value: The value to check.
    """
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError(f"{value} is an invalid positive int value")
    return ivalue


def check_non_negative_float(value: str) -> float:
    """Checks if the value is a non-negative float.

    Args:
        value: The value to check.
    """
    fvalue = float(value)
    if fvalue < 0:
        raise argparse.ArgumentTypeError(f"{value} must be non-negative")
    return fvalue


def args_parser() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(description="Evaluate H&M agent with queries from CSV.")

    parser.add_argument(
        "-c",
        "--cfg-path",
        type=str,
        default="./configs/config.yaml",
        help="Configuration file path.",
    )
    parser.add_argument(
        "-i",
        "--input-file",
        type=str,
        default="data/eval_test_set.csv",
        help="Path to the input CSV file containing queries.",
    )
    parser.add_argument(
        "-o",
        "--output-file",
        type=str,
        default="data/evaluation_results.xlsx",
        help="Path to the output excel file for results.",
    )
    parser.add_argument(
        "-m",
        "--max-concurrent",
        type=check_positive_int,
        default=1,
        help="Maximum number of concurrent requests.",
    )
    parser.add_argument(
        "-r",
        "--requests-per-second",
        type=check_non_negative_float,
        default=0.0,
        help="Maximum number of requests per second (0 for no limit).",
    )
    parser.add_argument(
        "--warmup-count",
        type=int,
        default=3,
        help="Number of warm-up queries to run before evaluation.",
    )
    parser.add_argument(
        "--agent-timeout",
        type=check_non_negative_float,
        default=120.0,
        help="Timeout in seconds for each agent query (0 to disable).",
    )
    parser.add_argument(
        "--http-timeout",
        type=check_non_negative_float,
        default=30.0,
        help="Timeout in seconds for HTTP image downloads (0 to disable).",
    )
    return parser.parse_args()


def read_input_data(file_path: str) -> pd.DataFrame:
    """Reads input data from a CSV file using pandas.

    Args:
        file_path: Path to the CSV file.

    Returns:
        DataFrame containing the queries.
    """
    path = Path(file_path)
    if not path.exists():
        logger.error("Input file not found: %s", file_path)
        raise FileNotFoundError(f"Input file not found: {file_path}")

    try:
        df = pd.read_csv(path)
        if "ImageURL" not in df.columns:
            raise ValueError("Input CSV must have a 'ImageURL' column.")
        return df
    except Exception:
        logger.exception("Error reading input file.")
        raise


def save_results(results: list[dict[str, Any]], file_path: str) -> None:
    """Saves evaluation results to an excel file.

    Args:
        results: List of result dictionaries.
        file_path: Path to the output excel file.
    """
    if not results:
        logger.warning("No results to save.")
        return

    try:
        df = pd.DataFrame(results)
        output_path = Path(file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(output_path, index=False)
        logger.info("Results saved to %s", file_path)
    except Exception:
        logger.exception("Error saving results.")
        raise


@dataclass(frozen=True)
class EvaluationConfig:
    """Configuration for the evaluation process."""

    max_concurrent: int
    requests_per_second: float
    warmup_count: int
    agent_timeout: float | None
    http_timeout: float | None


@dataclass
class ExecutionContext:
    """Context for query execution."""

    semaphore: asyncio.Semaphore
    download_semaphore: asyncio.Semaphore
    rate_limiter: asyncio.Queue[None] | None = field(default=None)


async def _download_with_retry(
    query: str,
    client: httpx.AsyncClient,
    download_semaphore: asyncio.Semaphore,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Any:
    """Download and process an image with concurrency control and retry logic.

    Args:
        query: The image URL / query string.
        client: Shared HTTP client.
        download_semaphore: Semaphore limiting concurrent downloads.
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds for exponential back-off.

    Returns:
        The processed `ImageType`.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            async with download_semaphore:
                return await process_image(query, client=client)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            last_exc = exc
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "Image download attempt %d/%d failed for '%s': %s - retrying in %.1fs",
                    attempt + 1,
                    max_retries,
                    query,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
    assert last_exc is not None, "max_retries must be >= 1"
    raise last_exc


async def process_single_query(
    runner: AgentRunner,
    query: str,
    context: ExecutionContext,
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    """Processes a single query with concurrency control.

    Image download is guarded by a separate download semaphore so that
    we do not overwhelm the image server.  The LLM agent call is
    guarded by the main semaphore and rate-limiter.

    Args:
        runner: The agent runner instance.
        query: The user query to process.
        context: The execution context.
        client: Shared HTTP client for image downloads.

    Returns:
        The result dictionary including latency and response.
    """
    try:
        image = await _download_with_retry(query, client, context.download_semaphore)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to download/process image for '%s': %s", query, e)
        return {"query": query, "latency_seconds": 0.0, "error": str(e)}

    if context.rate_limiter:
        await context.rate_limiter.get()

    async with context.semaphore:
        start_time = time.perf_counter()
        try:
            response = await runner.run(
                user_id=f"eval-user-{uuid.uuid4()}",
                session_id=str(uuid.uuid4()),
                user_input=image,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error processing query '%s': %s", query, e)
            response = json.dumps({"error": f"ERROR: {e}"})
        latency = time.perf_counter() - start_time

    try:
        response_dict = json.loads(response)
    except json.JSONDecodeError:
        response_dict = {"raw_response": response}

    return {"query": query, "latency_seconds": latency} | response_dict


async def _rate_limit_producer(queue: asyncio.Queue[None], rate: float, total: int) -> None:
    """Produces tokens into the queue at a specific rate.

    Args:
        queue: The queue to put tokens into.
        rate: The rate (tokens per second).
        total: Total number of tokens to produce.
    """
    interval = 1.0 / rate
    for _ in range(total):
        await queue.put(None)
        await asyncio.sleep(interval)


async def _run_warmup(
    valid_queries: list[str],
    warmup_count: int,
    runner: AgentRunner,
    client: httpx.AsyncClient,
) -> None:
    """Runs warm-up queries to initialize the agent.

    Args:
        valid_queries: List of valid queries.
        warmup_count: Number of warm-up queries to run.
        runner: The agent runner instance.
        client: Shared HTTP client for image downloads.
    """
    if warmup_count > 0 and valid_queries:
        logger.info("Running %d warm-up queries...", warmup_count)
        warmup_subset = random.sample(valid_queries, min(warmup_count, len(valid_queries)))
        for i, query in enumerate(warmup_subset, 1):
            logger.debug("Warm-up %d/%d: %s", i, len(warmup_subset), query)
            try:
                image = await process_image(query, client=client)
                await runner.run(
                    user_id=f"warmup-user-{uuid.uuid4()}",
                    session_id=str(uuid.uuid4()),
                    user_input=image,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Warm-up query failed: %s", e)
        logger.info("Warm-up complete. Starting main evaluation...\n")


def _create_execution_context(eval_config: EvaluationConfig) -> ExecutionContext:
    """Creates the execution context."""
    download_concurrency = max(eval_config.max_concurrent * 4, 20)
    return ExecutionContext(
        semaphore=asyncio.Semaphore(eval_config.max_concurrent),
        download_semaphore=asyncio.Semaphore(download_concurrency),
        rate_limiter=asyncio.Queue(maxsize=1) if eval_config.requests_per_second > 0 else None,
    )


def _calculate_and_log_stats(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculates and logs statistics for the evaluation results.

    Returns:
        A summary dict with avg/p95/p99 latencies, or empty dict when
        no results.
    """
    latencies = [r["latency_seconds"] for r in results if r.get("latency_seconds", 0) > 0]

    if not latencies:
        logger.warning("No valid queries processed.")
        return {}

    avg_latency = statistics.mean(latencies)

    if len(latencies) >= 2:
        quantile_cuts = statistics.quantiles(latencies, n=100)
        p95 = quantile_cuts[94]
        p99 = quantile_cuts[98]
    else:
        p95 = p99 = latencies[0]

    logger.info("Evaluation complete. Processed %d queries.", len(results))
    logger.info(
        "Latency - avg: %.4fs | p95: %.4fs | p99: %.4fs",
        avg_latency,
        p95,
        p99,
    )
    return {
        "query": "SUMMARY",
        "latency_seconds": avg_latency,
        "p95_seconds": p95,
        "p99_seconds": p99,
    }


async def process_queries(
    queries: list[str],
    config_path: str,
    eval_config: EvaluationConfig,
) -> list[dict[str, Any]]:
    """Runs queries against the agent and returns results.

    Args:
        queries: List of user queries.
        config_path: Path to the agent configuration.
        eval_config: Configuration for evaluation.

    Returns:
        List of evaluation results.
    """
    try:
        configs = load_config(config_path)
    except FileNotFoundError as e:
        logger.exception("Failed to load configuration: (%s: %s) ", type(e).__name__, e)
        return []

    logger.info("Initializing Restrictor Agent...")
    runner = AgentRunner(
        agent=create_restrictor_agent(configs.agents["restrictor"]),
        app_name="Restrictor-Eval-App",
        timeout=eval_config.agent_timeout,
    )

    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
        timeout=httpx.Timeout(eval_config.http_timeout, connect=10.0),
    ) as client:
        await _run_warmup(queries, eval_config.warmup_count, runner, client)

        logger.info(
            "Starting evaluation of %d queries (max_concurrent=%d, rps=%.1f)...\n",
            len(queries),
            eval_config.max_concurrent,
            eval_config.requests_per_second,
        )

        context = _create_execution_context(eval_config)

        rate_task: asyncio.Task[None] | None = None
        if context.rate_limiter:
            rate_task = asyncio.create_task(
                _rate_limit_producer(
                    context.rate_limiter, eval_config.requests_per_second, len(queries)
                )
            )

        tasks = [process_single_query(runner, query, context, client) for query in queries]
        results: list[dict[str, Any]] = await atqdm.gather(*tasks, desc="Evaluating")

        if rate_task:
            rate_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await rate_task

    summary = _calculate_and_log_stats(results)
    if summary:
        results.append(summary)

    return results


async def main() -> None:
    """Main function to orchestrate the evaluation."""
    setup_logger(keep_loggers=["__main__"])
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    args = args_parser()

    eval_config = EvaluationConfig(
        max_concurrent=args.max_concurrent,
        requests_per_second=args.requests_per_second,
        warmup_count=args.warmup_count,
        agent_timeout=args.agent_timeout or None,
        http_timeout=args.http_timeout or None,
    )

    try:
        logger.info("Reading input data from %s...", args.input_file)
        df = read_input_data(args.input_file)
        queries = df["ImageURL"].tolist()

        results = await process_queries(
            queries,
            args.cfg_path,
            eval_config,
        )

        logger.info("Saving results to %s...", args.output_file)
        save_results(results, args.output_file)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Evaluation failed: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
