# Alliance Restricted List

## What Is It?

The Alliance Restricted List (ARL) is a versioned list of cards with special restrictions in the Alliance format. Each version of the list (e.g., v2.5, v3.0) is stored in the database as an `AllianceRestrictedListVersion` record, with individual card entries in `AllianceRestrictedEntry`.

### How Restrictions Work

When a player forges an open Alliance deck (3 pods, 1 house each from different decks of the same set), the combined list of all cards across all 3 pods is checked against the current restricted list:

- **At most 1 entry type allowed**: An alliance may contain cards from at most **1 restricted entry** on the list. If pods collectively contain cards from 2 or more different restricted entries, the submission is rejected.
- **Max-copies limit**: Some entries have a `max_copies_per_alliance` field. If set, the total number of that card across all 3 pods may not exceed this limit.
- **Same-deck exemption**: If all 3 pods are chosen from the **same physical deck** (same `deck_id`), the restricted list check is skipped entirely.

## Reading the TRG PDF

The Tome of Restricted and Grimoire (TRG) PDF is Keyforge's official competitive document. It includes an Alliance Restricted List, typically as a table with:

- Card Name
- Maximum Copies Per Alliance (or "Any Number")

Look for the section titled "Alliance Restricted List" or similar.

## Populating a New Version

When a new TRG version is released:

1. Run the script once per card on the restricted list:

```bash
# Card with no copy limit (only 1 entry type allowed across alliance):
python keytracker/scripts/add_alliance_restricted_card.py --version 3.0 --card-name "Library Access"

# Card with a specific copy limit:
python keytracker/scripts/add_alliance_restricted_card.py --version 3.0 --card-name "Key Abduction" --max-copies 1
```

2. The script creates the version automatically if it does not exist.
3. Card names must exactly match `card_title` in `tracker_platonic_card`.

## Setting a Week/Match to Use a Specific Version

When creating or updating a league week or standalone match of type `alliance`, you can specify:

```json
{ "alliance_restricted_list_version_id": 3 }
```

If not specified, the latest version (highest `version` float) is used automatically.

## Example: TRG v2.5 Cards

```bash
python keytracker/scripts/add_alliance_restricted_card.py --version 2.5 --card-name "Reiteration"
python keytracker/scripts/add_alliance_restricted_card.py --version 2.5 --card-name "Key Abduction" --max-copies 1
python keytracker/scripts/add_alliance_restricted_card.py --version 2.5 --card-name "Strategic Feint"
```

## Migration SQL

If adding the restricted list tables to an existing database:

```sql
CREATE TABLE alliance_restricted_list_version (
    id INT PRIMARY KEY AUTO_INCREMENT,
    version FLOAT NOT NULL UNIQUE
);

CREATE TABLE alliance_restricted_entry (
    id INT PRIMARY KEY AUTO_INCREMENT,
    list_version_id INT NOT NULL REFERENCES alliance_restricted_list_version(id),
    platonic_card_id INT NOT NULL REFERENCES tracker_platonic_card(id),
    max_copies_per_alliance INT NULL
);

ALTER TABLE tracker_league_week
    ADD COLUMN alliance_restricted_list_version_id INT NULL REFERENCES alliance_restricted_list_version(id);

ALTER TABLE standalone_match
    ADD COLUMN alliance_restricted_list_version_id INT NULL REFERENCES alliance_restricted_list_version(id);

-- Extend the WeekFormat enum on standalone_match
ALTER TABLE standalone_match
    MODIFY format_type ENUM('archon_standard','triad','sealed_archon','sealed_alliance','thief','adaptive','alliance') NOT NULL;
```
