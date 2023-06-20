#!/usr/bin/env python3
import click
from flask import current_app, Flask
from flask.cli import AppGroup
import asyncio
from keytracker.schema import (
    db,
    Deck,
)
import click_log
from asyncio import create_task, Lock, Queue, Task
from typing import Iterable, List, Set
from keytracker.utils import (
    get_decks_from_page,
    get_deck_by_id_with_zeal,
    InternalServerError,
    RequestThrottled,
)
import time
import os
import json
import logging


collector = AppGroup("collector")
page_one_stopper = "/tmp/stop_page_one_loop"
click_log.basic_config()


@collector.command("get")
@click_log.simple_verbosity_option()
@click.option("--start-page", type=int, default=1)
@click.option("--max-pages", type=int, default=1)
@click.option("--page-workers", default=1)
@click.option("--deck-fetchers", default=1)
@click.option("--reverse/--no-reverse", default=False)
@click.option("-i", "--page-one-interval", type=int, default=0)
def get(
    start_page: int,
    max_pages: int,
    page_workers: int,
    deck_fetchers: int,
    reverse: bool,
    page_one_interval: int,
):
    logging.getLogger("aiohttp.client").setLevel(logging.INFO)
    asyncio.run(
        _get(
            start_page,
            max_pages,
            page_workers,
            deck_fetchers,
            reverse,
            page_one_interval,
        )
    )


async def _get(
    start_page: int,
    max_pages: int,
    page_workers: int,
    deck_fetchers: int,
    reverse: bool,
    page_one_interval: int,
):
    with current_app.app_context():
        known_deck_ids = {x[0] for x in db.session.query(Deck.id).all()}
    current_app.logger.info(f"Starting with {len(known_deck_ids)} decks in db.")
    page_queue = Queue()
    deck_queue = Queue()
    tasks = []
    current_app.logger.debug("Going to start tasks")
    tasks.extend(
        await start_page_fetchers(
            page_workers,
            page_queue,
            deck_queue,
            known_deck_ids,
        )
    )
    tasks.extend(
        await start_deck_fetchers(
            deck_fetchers,
            deck_queue,
        )
    )
    pages = range(start_page, max_pages + 1)
    if reverse:
        pages = reversed(pages)
    for page in pages:
        await page_queue.put(page)
    if page_one_interval:
        tailer = PageOneTailer(page_one_interval, deck_queue, known_deck_ids)
        page_one_task = create_task(tailer())
    await page_queue.join()
    if page_one_interval:
        await page_one_task
    await deck_queue.join()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


@collector.command("tail")
@click_log.simple_verbosity_option()
@click.option("-i", "--interval", type=int, default=300)
def tail(interval: int):
    logging.getLogger("aiohttp.client").setLevel(logging.INFO)
    asyncio.run(_tail(interval))


async def _tail(interval: int):
    with current_app.app_context():
        known_deck_ids = {x[0] for x in db.session.query(Deck.id).all()}
    current_app.logger.info(f"Starting tailer with {len(known_deck_ids)} decks in db.")
    deck_queue = Queue()
    tasks = []
    tasks.extend(
        await start_deck_fetchers(
            1,
            deck_queue,
            known_deck_ids,
        )
    )
    tailer = PageOneTailer(interval, deck_queue, known_deck_ids)
    tailer_task = create_task(tailer())
    await tailer_task
    await deck_queue.join()
    await db_queue.join()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def start_page_fetchers(
    workers: int,
    in_q: Queue,
    out_q: Queue,
    known_deck_ids: Set[str],
) -> Iterable[Task]:
    current_app.logger.debug("Starting page fetchers")
    fetcher = PageProcessor(in_q, out_q, known_deck_ids)
    return [create_task(fetcher(f"pager-{x}")) for x in range(workers)]


async def start_deck_fetchers(
    workers: int,
    in_q: Queue,
) -> Iterable[Task]:
    current_app.logger.debug("Starting deck fetchers")
    fetcher = DeckFetcher(in_q)
    return [create_task(fetcher(f"fetchers-{x}")) for x in range(workers)]


class PageProcessor:
    def __init__(self, in_q: Queue, out_q: Queue, known_deck_ids: Set[str]):
        self.in_q = in_q
        self.out_q = out_q
        self.known_deck_ids = known_deck_ids
        self.counter = 0
        self.counter_lock = Lock()

    async def __call__(self, iname: str) -> None:
        skipped_decks = 0
        ise_in_a_row = 0
        current_app.logger.debug(f"{iname}:Starting up")
        while True:
            page = await self.in_q.get()
            self.in_q.task_done()
            if page % 10 == 0:
                current_app.logger.info(f"{iname}:Getting page {page}")
            try:
                decks = await get_decks_from_page(page)
                if ise_in_a_row > 0:
                    current_app.logger.info(
                        f"{iname}:Had {ise_in_a_row} InternalServerErrors. " "Clearing."
                    )
                ise_in_a_row = 0
            except InternalServerError:
                ise_in_a_row += 1
                if ise_in_a_row > 5:
                    current_app.logger.exception(
                        f"{iname}:Got InternalServerError 5x in a row. STOPPING"
                    )
                    return
                continue
            except RequestThrottled:
                current_app.logger.exception(
                    f"{iname}:RequestThrottled bubbled up from page {page}"
                )
                continue
            except json.decoder.JSONDecodeError:
                current_app.logger.error(f"{iname}:JSONDecodeError getting page {page}")
                continue
            except KeyError:
                current_app.logger.exception(f"{iname}:KeyError getting page {page}")
                continue
            except Exception:
                current_app.logger.exception(f"{iname}:Exception getting page {page}")
                continue
            for deck_id in decks:
                if deck_id in self.known_deck_ids:
                    continue
                await self.out_q.put(deck_id)
                self.known_deck_ids.add(deck_id)


class DeckFetcher:
    def __init__(self, q: Queue):
        self.q = q
        self.counter = 0
        self.counter_lock = Lock()

    async def __call__(self, iname: str) -> None:
        current_app.logger.debug(f"{iname}:Starting up")
        with current_app.app_context():
            while True:
                deck_id = await self.q.get()
                get_deck_by_id_with_zeal(deck_id)
                async with self.counter_lock:
                    self.counter += 1
                    if self.counter % 1 == 0:
                        current_app.logger.debug(
                            f"{iname}:{self.counter} decks processed"
                        )


class PageOneTailer:
    def __init__(
        self,
        loop_interval: int,
        out_q: Queue,
        known_deck_ids: Set[str],
        stopper: str = page_one_stopper,
    ):
        self.loop_interval = loop_interval
        self.out_q = out_q
        self.known_deck_ids = known_deck_ids
        self.stopper = stopper

    async def __call__(self):
        name = "p1_tailer"
        decks_added = 0
        current_app.logger.debug(f"{name}:Starting up")
        while True and not os.path.exists(self.stopper):
            loop_start = time.time()
            end_iter = False
            page = 1
            while not end_iter:
                decks = await get_decks_from_page(page)
                page += 1
                for deck_id in decks:
                    if deck_id in self.known_deck_ids:
                        end_iter = True
                        continue
                    await self.out_q.put(deck_id)
                    self.known_deck_ids.add(deck_id)
                    decks_added += 1
                    current_app.logger.debug(f"{name}:found {decks_added} decks so far")
            current_app.logger.debug(
                f"{name}:Page One Getter checked {page - 1} pages this iteration"
            )
            loop_end = time.time()
            to_sleep = loop_start + self.loop_interval - loop_end
            if to_sleep > 0:
                current_app.logger.debug(
                    f"{name}:Page One Getter sleeping for {to_sleep}"
                )
                await asyncio.sleep(to_sleep)
            else:
                current_app.logger.debug(f"{name}:Page One Getter not sleeping")
        os.remove(self.stopper)
