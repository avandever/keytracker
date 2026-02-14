from keytracker.schema import Deck, Game, Log, HouseTurnCounts, EXPANSION_ID_TO_ABBR


def serialize_game_summary(game: Game) -> dict:
    return {
        "crucible_game_id": game.crucible_game_id,
        "date": game.date.isoformat() if game.date else None,
        "winner": game.winner,
        "loser": game.loser,
        "winner_keys": game.winner_keys,
        "loser_keys": game.loser_keys,
        "winner_deck_name": game.winner_deck_name,
        "loser_deck_name": game.loser_deck_name,
        "winner_deck_id": game.winner_deck.kf_id if game.winner_deck else None,
        "loser_deck_id": game.loser_deck.kf_id if game.loser_deck else None,
        "winner_sas_rating": game.winner_deck.sas_rating if game.winner_deck else None,
        "loser_sas_rating": game.loser_deck.sas_rating if game.loser_deck else None,
        "winner_aerc_score": game.winner_deck.aerc_score if game.winner_deck else None,
        "loser_aerc_score": game.loser_deck.aerc_score if game.loser_deck else None,
        "first_player": game.insist_first_player,
    }


def serialize_log(log: Log) -> dict:
    return {
        "message": log.message,
        "time": log.time.isoformat() if log.time else None,
        "winner_perspective": log.winner_perspective,
    }


def serialize_house_turn_count(htc: HouseTurnCounts) -> dict:
    return {
        "player": htc.player.username if htc.player else None,
        "house": htc.house,
        "turns": htc.turns,
        "winner": htc.winner,
    }


def serialize_game_detail(game: Game) -> dict:
    data = serialize_game_summary(game)
    data["logs"] = [serialize_log(log) for log in game.logs]
    data["house_turn_counts"] = [
        serialize_house_turn_count(htc) for htc in game.house_turn_counts
    ]
    return data


def serialize_deck_summary(deck: Deck) -> dict:
    return {
        "kf_id": deck.kf_id,
        "name": deck.name,
        "expansion": deck.expansion,
        "expansion_name": EXPANSION_ID_TO_ABBR.get(deck.expansion, "Unknown"),
        "sas_rating": deck.sas_rating,
        "aerc_score": deck.aerc_score,
        "mv_url": deck.mv_url,
        "dok_url": deck.dok_url,
    }


def serialize_deck_detail(deck: Deck) -> dict:
    data = serialize_deck_summary(deck)
    data["houses"] = sorted(
        [ps.house for ps in deck.pod_stats if ps.house != "Archon Power"]
    )
    data["pod_stats"] = [
        {
            "house": ps.house,
            "sas_rating": ps.sas_rating,
            "aerc_score": ps.aerc_score,
            "enhanced_amber": ps.enhanced_amber,
            "enhanced_capture": ps.enhanced_capture,
            "enhanced_draw": ps.enhanced_draw,
            "enhanced_damage": ps.enhanced_damage,
            "enhanced_discard": ps.enhanced_discard,
            "num_enhancements": ps.num_enhancements,
            "num_mutants": ps.num_mutants,
            "creatures": ps.creatures,
            "raw_amber": ps.raw_amber,
            "total_amber": ps.total_amber,
        }
        for ps in deck.pod_stats
        if ps.house != "Archon Power"
    ]
    return data
