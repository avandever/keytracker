-- Index tracker_game.date, which nothing indexes today.
--
-- Every listing of games orders by date descending and takes a page:
-- /api/v2/games/recent, /games/mine, and the default games search. With no
-- index MySQL scans the whole table and sorts it to return five rows --
-- 456k rows and 190MB as of October 2026, measured at 0.69s for the sort
-- against 0.003s for the same query ordered by an indexed column.
--
-- Costs roughly 10MB of index on a 190MB table, and one more B-tree per
-- game insert, which arrive a handful at a time.
--
-- MySQL 8 builds this online, so it does not lock the table against reads
-- or writes. Still worth running off-peak: it reads every row to build.
--
-- Safe to re-run only after checking, as MySQL has no IF NOT EXISTS for an
-- index. To check first:
--     SHOW INDEX FROM tracker_game WHERE Key_name = 'ix_tracker_game_date';

ALTER TABLE tracker_game
    ADD INDEX ix_tracker_game_date (date),
    ALGORITHM=INPLACE, LOCK=NONE;
