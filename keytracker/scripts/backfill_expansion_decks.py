#!/usr/bin/env python3
"""Walk Master Vault for a single expansion and ingest every deck in it.

The main crawler advances one page pointer through the whole catalogue in
date order and never goes back, so a set it got ahead of stays permanently
under-represented. Draconian Measures sat at 806 of 25,419 decks that way,
which skewed sealed pool generation towards decks players had registered
here rather than the set at large.

This walks the expansion-filtered listing instead, leaving
highest_mv_page_scraped alone, and reuses add_one_deck_v2 so decks are
ingested exactly as the normal crawl would ingest them.

Resumable: pass --start-page to continue, and existing decks are repaired
rather than duplicated.

    EXPANSION=928 python3 keytracker/scripts/backfill_expansion_decks.py
"""
import os
import time

from keytracker.schema import db, Deck
from keytracker.utils import get_decks_from_page_v2, InternalServerError

EXPANSION = int(os.environ.get("EXPANSION", "928"))
START_PAGE = int(os.environ.get("START_PAGE", "1"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "0")) or None
PROGRESS_EVERY = int(os.environ.get("PROGRESS_EVERY", "25"))


def main():
    from keytracker.server import app

    with app.app_context():
        before = Deck.query.filter_by(expansion=EXPANSION).count()
        print(f"expansion {EXPANSION}: {before:,} decks known before", flush=True)

        add_decks_cache = {
            "seen_deck_ids": set(),
            "card_in_set": {},
            "platonic_card": {},
        }

        page = START_PAGE
        pages_done = 0
        new_total = 0
        empty_pages = 0
        started = time.time()

        while MAX_PAGES is None or pages_done < MAX_PAGES:
            try:
                new_decks = get_decks_from_page_v2(
                    page,
                    reverse=True,
                    add_decks_cache=add_decks_cache,
                    update_highest_page=False,
                    expansion=EXPANSION,
                )
            except InternalServerError:
                print(f"page {page} is past the end; stopping", flush=True)
                break
            except Exception as exc:
                print(f"page {page} failed ({type(exc).__name__}), retrying once",
                      flush=True)
                db.session.rollback()
                time.sleep(10)
                try:
                    new_decks = get_decks_from_page_v2(
                        page,
                        reverse=True,
                        add_decks_cache=add_decks_cache,
                        update_highest_page=False,
                        expansion=EXPANSION,
                    )
                except Exception:
                    print(f"page {page} failed again; skipping", flush=True)
                    db.session.rollback()
                    page += 1
                    pages_done += 1
                    continue

            new_total += new_decks
            page += 1
            pages_done += 1

            # A run of pages holding nothing new means the listing is exhausted.
            empty_pages = empty_pages + 1 if new_decks == 0 else 0
            if empty_pages >= 5:
                print(f"5 consecutive pages with no new decks; stopping at {page}",
                      flush=True)
                break

            if pages_done % PROGRESS_EVERY == 0:
                elapsed = time.time() - started
                current = Deck.query.filter_by(expansion=EXPANSION).count()
                print(
                    f"[page {page}] pages={pages_done} new={new_total} "
                    f"total_now={current:,} "
                    f"{pages_done / elapsed:.2f} pages/s",
                    flush=True,
                )

        after = Deck.query.filter_by(expansion=EXPANSION).count()
        print(
            f"\nDONE in {(time.time() - started) / 60:.1f}m: "
            f"pages={pages_done} newly_added={new_total} "
            f"expansion {EXPANSION} now {after:,} decks (was {before:,})",
            flush=True,
        )


if __name__ == "__main__":
    main()
