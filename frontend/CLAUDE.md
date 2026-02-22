# Frontend CLAUDE.md

## Frontend/Backend Sync

Certain TypeScript types in `src/types.ts` manually mirror Python enums from `keytracker/schema.py`. When modifying these enums, update both sides:

- `WeekStatus` type in `src/types.ts` ↔ `WeekStatus` enum in `keytracker/schema.py`
