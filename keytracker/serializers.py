from keytracker.schema import (
    Deck,
    Game,
    Log,
    HouseTurnCounts,
    League,
    LeagueSignup,
    LeagueWeek,
    WeekMatchup,
    PlayerMatchup,
    PlayerDeckSelection,
    MatchGame,
    Team,
    TeamMember,
    EXPANSION_ID_TO_ABBR,
)
import json


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
        "db_id": deck.id,
        "kf_id": deck.kf_id,
        "name": deck.name,
        "expansion": deck.expansion,
        "expansion_name": EXPANSION_ID_TO_ABBR.get(deck.expansion, "Unknown"),
        "sas_rating": deck.sas_rating,
        "aerc_score": deck.aerc_score,
        "mv_url": deck.mv_url,
        "dok_url": deck.dok_url,
        "houses": sorted(
            [ps.house for ps in deck.pod_stats if ps.house != "Archon Power"]
        ),
    }


def serialize_deck_detail(deck: Deck) -> dict:
    data = serialize_deck_summary(deck)
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


def serialize_user_brief(user) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "is_test_user": user.is_test_user,
    }


def serialize_team_member(member: TeamMember) -> dict:
    return {
        "id": member.id,
        "user": serialize_user_brief(member.user),
        "is_captain": member.is_captain,
        "has_paid": member.has_paid,
    }


def serialize_team_detail(team: Team) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "order_number": team.order_number,
        "members": [serialize_team_member(m) for m in team.members],
    }


def serialize_signup(signup: LeagueSignup) -> dict:
    return {
        "id": signup.id,
        "user": serialize_user_brief(signup.user),
        "signup_order": signup.signup_order,
        "status": signup.status,
        "signed_up_at": (
            signup.signed_up_at.isoformat() if signup.signed_up_at else None
        ),
    }


def serialize_league_summary(league: League) -> dict:
    return {
        "id": league.id,
        "name": league.name,
        "description": league.description,
        "fee_amount": (
            float(league.fee_amount) if league.fee_amount is not None else None
        ),
        "team_size": league.team_size,
        "num_teams": league.num_teams,
        "status": league.status,
        "week_bonus_points": league.week_bonus_points,
        "is_test": league.is_test,
        "created_by": serialize_user_brief(league.created_by),
        "signup_count": len(league.signups),
        "created_at": league.created_at.isoformat() if league.created_at else None,
    }


def serialize_league_detail(league: League, viewer=None) -> dict:
    data = serialize_league_summary(league)
    data["teams"] = [
        serialize_team_detail(t)
        for t in sorted(league.teams, key=lambda t: t.order_number)
    ]
    data["signups"] = [
        serialize_signup(s)
        for s in sorted(league.signups, key=lambda s: s.signup_order)
    ]
    data["admins"] = [serialize_user_brief(a.user) for a in league.admins]
    data["weeks"] = [
        serialize_league_week(w, viewer=viewer)
        for w in sorted(league.weeks, key=lambda w: w.week_number)
    ]
    return data


def serialize_league_week(week: LeagueWeek, viewer=None) -> dict:
    allowed_sets = None
    if week.allowed_sets:
        try:
            allowed_sets = json.loads(week.allowed_sets)
        except (json.JSONDecodeError, TypeError):
            allowed_sets = None

    # Player matchups are hidden from non-admins until the week is published
    viewer_is_admin = viewer and any(a.user_id == viewer.id for a in week.league.admins)
    show_player_matchups = week.status != "pairing" or viewer_is_admin

    data = {
        "id": week.id,
        "league_id": week.league_id,
        "week_number": week.week_number,
        "name": week.name,
        "format_type": week.format_type,
        "status": week.status,
        "best_of_n": week.best_of_n,
        "allowed_sets": allowed_sets,
        "max_sas": week.max_sas,
        "combined_max_sas": week.combined_max_sas,
        "set_diversity": week.set_diversity,
        "house_diversity": week.house_diversity,
        "decks_per_player": week.decks_per_player,
        "sealed_pools_generated": week.sealed_pools_generated,
        "matchups": [
            serialize_week_matchup(
                m, viewer=viewer, show_player_matchups=show_player_matchups
            )
            for m in week.matchups
        ],
        "deck_selections": [
            serialize_deck_selection(ds) for ds in week.deck_selections
        ],
        "feature_designations": [
            {"team_id": fd.team_id, "user_id": fd.user_id}
            for fd in week.feature_designations
        ],
    }
    return data


def serialize_week_matchup(
    matchup: WeekMatchup, viewer=None, show_player_matchups: bool = True
) -> dict:
    return {
        "id": matchup.id,
        "week_id": matchup.week_id,
        "team1": serialize_team_detail(matchup.team1),
        "team2": serialize_team_detail(matchup.team2),
        "player_matchups": (
            [
                serialize_player_matchup(pm, viewer=viewer)
                for pm in matchup.player_matchups
            ]
            if show_player_matchups
            else []
        ),
    }


def serialize_player_matchup(pm: PlayerMatchup, viewer=None) -> dict:
    data = {
        "id": pm.id,
        "week_matchup_id": pm.week_matchup_id,
        "player1": serialize_user_brief(pm.player1),
        "player2": serialize_user_brief(pm.player2),
        "player1_started": pm.player1_started,
        "player2_started": pm.player2_started,
        "is_feature": pm.is_feature,
        "games": [
            serialize_match_game(g)
            for g in sorted(pm.games, key=lambda g: g.game_number)
        ],
    }
    # Include strike info
    data["strikes"] = [
        {
            "striking_user_id": s.striking_user_id,
            "struck_deck_selection_id": s.struck_deck_selection_id,
        }
        for s in pm.strikes
    ]
    return data


def serialize_deck_selection(sel: PlayerDeckSelection) -> dict:
    deck_data = None
    if sel.deck:
        deck_data = serialize_deck_summary(sel.deck)
        deck_data["db_id"] = sel.deck.id
    return {
        "id": sel.id,
        "week_id": sel.week_id,
        "user_id": sel.user_id,
        "slot_number": sel.slot_number,
        "deck": deck_data,
    }


def serialize_match_game(game: MatchGame) -> dict:
    return {
        "id": game.id,
        "player_matchup_id": game.player_matchup_id,
        "game_number": game.game_number,
        "winner_id": game.winner_id,
        "player1_keys": game.player1_keys,
        "player2_keys": game.player2_keys,
        "went_to_time": game.went_to_time,
        "loser_conceded": game.loser_conceded,
        "player1_deck_id": game.player1_deck_id,
        "player2_deck_id": game.player2_deck_id,
        "reported_by_id": game.reported_by_id,
        "created_at": game.created_at.isoformat() if game.created_at else None,
    }
