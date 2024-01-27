#!/usr/bin/env python3
import click
from flask import current_app, Flask
from flask.cli import AppGroup
import asyncio
from keytracker.schema import (
    db,
    PlatonicCard,
    Deck,
)
from aiohttp_requests import requests as arequests
import click_log
from asyncio import create_task, Lock, Queue, Task
from typing import Iterable, List, Set
from keytracker.utils import (
    get_decks_from_page,
    get_decks_from_page_v2,
    get_deck_by_id_with_zeal,
    InternalServerError,
    RequestThrottled,
)
import time
import os
import json
import logging
import shutil


collector = AppGroup("collector")
page_one_stopper = "/tmp/stop_page_one_loop"
click_log.basic_config()


@collector.command("get_images")
@click_log.simple_verbosity_option()
@click.option("--image-dir", default="keyforge-images")
@click.option("--group-by", default="expansion,house,rarity,card_type")
def get_images(image_dir: str, group_by: str) -> None:
    asyncio.run(_get_images(
        image_dir,
        group_by=group_by.split(",")
    ))


async def _get_images(image_dir: str, group_by: List[str] = None) -> None:
    with current_app.app_context():
        all_cards = PlatonicCard.query.all()
        for card in all_cards:
            await get_card_image(
                card,
                image_dir,
                group_by,
            )


def build_image_dirs(
    base_dir: str,
    card: PlatonicCard,
    group_by: List[str] = None,
) -> List[str]:
    if group_by is None:
        return base_dir
    if "expansion" in group_by:
        expansions = card.expansions
    else:
        expansions = [""]
    paths = []
    for expansion in expansions:
        path_bits = [base_dir]
        path_bits.append("-".join(group_by))
        for attr in group_by:
            if attr == "expansion":
                path_bits.append(str(expansion.expansion))
            else:
                try:
                    bit = getattr(card, attr)
                except AttributeError:
                    bit = getattr(expansion, attr)
                path_bits.append(str(bit))
        paths.append(os.path.join(*path_bits))
    return paths


async def get_card_image(
    card: PlatonicCard,
    image_dir: str,
    group_by: List[str] = None,
) -> None:
    group_by_paths = build_image_dirs(image_dir, card, group_by)
    output_file = os.path.join(image_dir, os.path.basename(card.front_image))
    group_by_links = [
        os.path.join(
            group_by_path,
            os.path.basename(card.front_image),
        )
        for group_by_path in group_by_paths
    ]
    if not os.path.exists(output_file):
        img = await arequests.get(card.front_image)
        with open(output_file, "wb") as fh:
            fh.write(await img.content.read())
    for group_by_link in group_by_links:
        if not os.path.exists(group_by_link):
            os.makedirs(os.path.dirname(group_by_link), exist_ok=True)
            shutil.copy(output_file, group_by_link)


@collector.command("get_v2")
@click_log.simple_verbosity_option()
@click.option("--start-page", type=int, default=1)
@click.option("--max-pages", type=int, default=1)
@click.option("--reverse/--no-reverse", default=False)
@click.option("--seconds-per-request", type=int, default=10)
@click.option("-i", "--page-one-interval", type=int, default=0)
def get_v2(
    start_page: int,
    max_pages: int,
    reverse: bool,
    seconds_per_request: int,
    page_one_interval: int,
) -> None:
    logging.debug("Starting collector")
    end_page = start_page + max_pages
    start_time = time.time()
    last_page_one_run = 0
    pages_done = 0
    last_run = 0
    for page in range(start_page, end_page):
        now = time.time()
        if page_one_interval and now - last_page_one_run > page_one_interval:
            pages_done += get_page_one_v2(seconds_per_request)
            now = time.time()
        delta = now - last_run
        if delta < seconds_per_request:
            to_sleep = seconds_per_request - delta
            logging.debug(f"Sleeping {to_sleep}")
            time.sleep(to_sleep)
        last_run = time.time()
        logging.debug(
            f"Getting page {page} (stopping at {end_page}), reverse={reverse}. "
            f"{pages_done} pages done in {last_run - start_time} seconds. "
            f"1 page per {(last_run - start_time) / (pages_done or 1)} seconds."
        )
        with current_app.app_context():
            get_decks_from_page_v2(page, reverse=reverse)
        pages_done += 1


def get_page_one_v2(seconds_per_request: int) -> int:
    last_run = 0
    run_count = 0
    new_deck_count = -1
    page = 0
    while new_deck_count == -1 or new_deck_count > 20:
        page += 1
        now = time.time()
        delta = now - last_run
        if delta < seconds_per_request:
            to_sleep = seconds_per_request - delta
            logging.debug(f"Sleeping {to_sleep}")
            time.sleep(to_sleep)
        last_run = time.time()
        with current_app.app_context():
            new_deck_count = get_decks_from_page_v2(1, reverse=False)
        logging.debug(f"Found {new_deck_count} new decks on page {page}")
        run_count += 1
    return run_count


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
    logging.debug("Starting collector")
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
        known_deck_ids = {x[0] for x in db.session.query(Deck.kf_id).all()}
    current_app.logger.info(f"Starting with {len(known_deck_ids)} decks in db.")
    current_app.logger.info(f"Example deck id: {list(known_deck_ids)[0]}")
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
    return [create_task(fetcher(f"fetcher-{x}")) for x in range(workers)]


class PageProcessor:
    def __init__(self, in_q: Queue, out_q: Queue, known_deck_ids: Set[str]):
        self.in_q = in_q
        self.out_q = out_q
        self.known_deck_ids = known_deck_ids
        self.decks_skipped = 0

    async def __call__(self, iname: str) -> None:
        skipped_decks = 0
        ise_in_a_row = 0
        current_app.logger.debug(f"{iname}:Starting up")
        while True:
            page = await self.in_q.get()
            if page % 10 == 0:
                current_app.logger.info(f"{iname}:Getting page {page}")
            self.in_q.task_done()
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
                    skipped_decks += 1
                    if skipped_decks % 100 == 0:
                        current_app.logger.debug(f"{iname}: Skipped {skipped_decks}")
                    continue
                await self.out_q.put(deck_id)
                self.known_deck_ids.add(deck_id)


class DeckFetcher:
    def __init__(self, q: Queue):
        self.q = q
        self.counter = 0
        self.skip_counter = 0

    async def __call__(self, iname: str) -> None:
        current_app.logger.debug(f"{iname}:Starting up")
        with current_app.app_context():
            while True:
                deck_id = await self.q.get()
                # This will happen again inside get_deck_by_id_with_zeal, but then we
                # won't know whether the deck was already in db or freshly fetched
                deck = Deck.query.filter_by(kf_id=deck_id).first()
                if deck is not None:
                    self.skip_counter += 1
                    if self.skip_counter % 100 == 0:
                        current_app.logger.debug(
                            f"{iname}:{self.skip_counter} decks skipped"
                        )
                    continue
                get_deck_by_id_with_zeal(deck_id)
                self.counter += 1
                if self.counter % 100 == 0:
                    current_app.logger.debug(f"{iname}:{self.counter} decks fetched")


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


if __name__ == "__main__":
    collector()
