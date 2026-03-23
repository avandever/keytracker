from keytracker.schema import (
    Deck,
    ExtendedGameData,
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
    SealedPoolDeck,
    AlliancePodSelection,
    AllianceRestrictedListVersion,
    ThiefCurationDeck,
    ThiefSteal,
    LeagueAdminLog,
    EXPANSION_ID_TO_ABBR,
)
from keytracker.schema import StandaloneMatch, PlatonicCard, PlatonicCardInSet, db
from sqlalchemy import select
import json


def serialize_extended_data(ext: ExtendedGameData) -> dict:
    return {
        "submitter_username": ext.submitter_username,
        "extension_version": ext.extension_version,
        "turn_timing": ext.turn_timing or [],
        "player2_username": ext.player2_username,
        "player2_extension_version": ext.player2_extension_version,
        "player2_turn_timing": ext.player2_turn_timing or [],
        "key_events": ext.key_events or [],
        "player2_key_events": ext.player2_key_events or [],
        "turn_snapshots": ext.turn_snapshots or [],
        "player2_turn_snapshots": ext.player2_turn_snapshots or [],
        "both_perspectives": ext.both_perspectives,
    }


def serialize_restricted_list_version(v: AllianceRestrictedListVersion) -> dict:
    return {"id": v.id, "version": v.version}


def serialize_game_summary(game: Game) -> dict:
    return {
        "crucible_game_id": game.crucible_game_id,
        "date": game.date.isoformat() + "Z" if game.date else None,
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
        "has_extended_data": game.extended_data is not None,
    }


def serialize_log(log: Log) -> dict:
    return {
        "message": log.message,
        "time": log.time.isoformat() + "Z" if log.time else None,
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
    data["extended_data"] = (
        serialize_extended_data(game.extended_data) if game.extended_data else None
    )
    rows = db.session.execute(
        select(PlatonicCard.card_title, PlatonicCardInSet.front_image)
        .join(PlatonicCardInSet, PlatonicCardInSet.card_id == PlatonicCard.id)
        .where(PlatonicCardInSet.front_image.isnot(None))
    ).all()
    card_images = {title: img for title, img in rows if title}
    data["card_images"] = card_images
    return data


def serialize_deck_brief(deck: Deck) -> dict:
    return {
        "db_id": deck.id,
        "kf_id": deck.kf_id,
        "name": deck.name,
        "expansion": deck.expansion,
        "expansion_name": EXPANSION_ID_TO_ABBR.get(deck.expansion, "Unknown"),
        "sas_rating": deck.sas_rating,
        "mv_url": deck.mv_url,
        "dok_url": deck.dok_url,
        "houses": sorted(
            [ps.house for ps in deck.pod_stats if ps.house != "Archon Power"]
        ),
    }


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
    tco = [t.username for t in (user.tco_usernames or [])]
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "is_test_user": user.is_test_user,
        "tco_username": tco[0] if tco else None,
        "discord_username": user.discord_username,
        "dok_profile_url": user.dok_profile_url,
    }


def serialize_team_member(member: TeamMember) -> dict:
    return {
        "id": member.id,
        "user": serialize_user_brief(member.user),
        "is_captain": member.is_captain,
        "has_paid": member.has_paid,
    }


def serialize_team_detail(team: Team, hide_members: bool = False) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "order_number": team.order_number,
        "allow_peer_deck_entry": bool(team.allow_peer_deck_entry),
        "members": [] if hide_members else [serialize_team_member(m) for m in team.members],
    }


def serialize_signup(signup: LeagueSignup) -> dict:
    return {
        "id": signup.id,
        "user": serialize_user_brief(signup.user),
        "signup_order": signup.signup_order,
        "status": signup.status,
        "signed_up_at": (
            signup.signed_up_at.isoformat() + "Z" if signup.signed_up_at else None
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
        "url_name": league.url_name,
        "created_by": serialize_user_brief(league.created_by),
        "signup_count": len(league.signups),
        "created_at": (
            league.created_at.isoformat() + "Z" if league.created_at else None
        ),
    }


def serialize_league_detail(
    league: League, viewer=None, hide_team_members: bool = False
) -> dict:
    data = serialize_league_summary(league)
    data["teams"] = [
        serialize_team_detail(t, hide_members=hide_team_members)
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

    # Alliance pod selections for the viewer's team (so teammates are visible)
    alliance_selections = []
    if viewer and week.format_type in ("sealed_alliance", "alliance"):
        viewer_team_member_ids = {viewer.id}
        for team in week.league.teams:
            member_ids = {m.user_id for m in team.members}
            if viewer.id in member_ids:
                viewer_team_member_ids = member_ids
                break
        alliance_selections = AlliancePodSelection.query.filter(
            AlliancePodSelection.week_id == week.id,
            AlliancePodSelection.user_id.in_(viewer_team_member_ids),
        ).all()

    # Thief curation and steals data
    thief_curation_decks = []
    thief_steals = []
    thief_floor_team_id = None
    if week.format_type == "thief":
        thief_curation_decks = ThiefCurationDeck.query.filter_by(week_id=week.id).all()
        thief_steals = ThiefSteal.query.filter_by(week_id=week.id).all()
        thief_floor_team_id = week.thief_floor_team_id

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
        "sas_floor": week.sas_floor,
        "combined_max_sas": week.combined_max_sas,
        "set_diversity": week.set_diversity,
        "house_diversity": week.house_diversity,
        "decks_per_player": week.decks_per_player,
        "sealed_pools_generated": week.sealed_pools_generated,
        "no_keycheat": week.no_keycheat,
        "custom_description": week.custom_description,
        "hide_standard_description": week.hide_standard_description,
        "thief_floor_team_id": thief_floor_team_id,
        "alliance_restricted_list_version": (
            serialize_restricted_list_version(week.alliance_restricted_list_version)
            if getattr(week, "alliance_restricted_list_version_id", None)
            and week.alliance_restricted_list_version
            else None
        ),
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
        "feature_volunteers": [
            {"team_id": fv.team_id, "user_id": fv.user_id}
            for fv in week.feature_volunteers
        ],
        "deck_suggestions": [
            {
                "id": ds.id,
                "team_id": ds.team_id,
                "suggesting_user_id": ds.suggesting_user_id,
                "deck": serialize_deck_summary(ds.deck) if ds.deck else None,
            }
            for ds in week.deck_suggestions
        ],
        "alliance_selections": [
            serialize_alliance_selection(s) for s in alliance_selections
        ],
        "thief_curation_decks": [
            {
                "id": cd.id,
                "team_id": cd.team_id,
                "slot_number": cd.slot_number,
                "deck": serialize_deck_summary(cd.deck) if cd.deck else None,
            }
            for cd in thief_curation_decks
        ],
        "thief_steals": [
            {
                "id": s.id,
                "stealing_team_id": s.stealing_team_id,
                "curation_deck_id": s.curation_deck_id,
            }
            for s in thief_steals
        ],
        "sas_ladder_maxes": (
            json.loads(week.sas_ladder_maxes) if week.sas_ladder_maxes else None
        ),
        "sas_ladder_feature_rung": week.sas_ladder_feature_rung,
        "sas_ladder_assignments": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "team_id": a.team_id,
                "rung_number": a.rung_number,
            }
            for a in (week.sas_ladder_assignments or [])
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
        "thief_stolen_team_id": matchup.thief_stolen_team_id,
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
    from keytracker.match_helpers import get_adaptive_winning_deck_player_id

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
        "adaptive_bid_chains": pm.adaptive_bid_chains,
        "adaptive_bidder_id": pm.adaptive_bidder_id,
        "adaptive_bidding_complete": pm.adaptive_bidding_complete,
        "adaptive_winning_deck_player_id": get_adaptive_winning_deck_player_id(pm),
    }
    # Include strike info
    data["strikes"] = [
        {
            "striking_user_id": s.striking_user_id,
            "struck_deck_selection_id": s.struck_deck_selection_id,
        }
        for s in pm.strikes
    ]
    # Triad Short picks — revealed simultaneously when both have submitted
    triad_picks = getattr(pm, "triad_short_picks", [])
    data["triad_short_picks_count"] = len(triad_picks)
    data["triad_short_picks"] = (
        [
            {
                "picking_user_id": p.picking_user_id,
                "picked_deck_selection_id": p.picked_deck_selection_id,
            }
            for p in triad_picks
        ]
        if len(triad_picks) == 2
        else []
    )
    # Adaptive Short choices and bid state
    adaptive_short_choices = getattr(pm, "adaptive_short_choices", [])
    data["adaptive_short_choices_count"] = len(adaptive_short_choices)
    data["adaptive_short_choices"] = (
        [
            {
                "choosing_user_id": c.choosing_user_id,
                "chosen_deck_selection_id": c.chosen_deck_selection_id,
            }
            for c in adaptive_short_choices
        ]
        if len(adaptive_short_choices) == 2
        else []
    )
    data["adaptive_short_bid_chains"] = getattr(pm, "adaptive_short_bid_chains", None)
    data["adaptive_short_bidder_id"] = getattr(pm, "adaptive_short_bidder_id", None)
    data["adaptive_short_bidding_complete"] = getattr(
        pm, "adaptive_short_bidding_complete", False
    )
    # Oubliette banned houses and eligible deck IDs
    data["oubliette_p1_banned_house"] = getattr(pm, "oubliette_p1_banned_house", None)
    data["oubliette_p2_banned_house"] = getattr(pm, "oubliette_p2_banned_house", None)
    if pm.oubliette_p1_banned_house and pm.oubliette_p2_banned_house:
        from keytracker.match_helpers import get_oubliette_eligible_deck_ids

        if pm.standalone_match_id:
            p1_sels = PlayerDeckSelection.query.filter_by(
                standalone_match_id=pm.standalone_match_id, user_id=pm.player1_id
            ).all()
            p2_sels = PlayerDeckSelection.query.filter_by(
                standalone_match_id=pm.standalone_match_id, user_id=pm.player2_id
            ).all()
        elif pm.week_matchup_id:
            from keytracker.schema import WeekMatchup

            wm = db.session.get(WeekMatchup, pm.week_matchup_id)
            week_id = wm.week_id if wm else None
            p1_sels = (
                PlayerDeckSelection.query.filter_by(
                    week_id=week_id, user_id=pm.player1_id
                ).all()
                if week_id
                else []
            )
            p2_sels = (
                PlayerDeckSelection.query.filter_by(
                    week_id=week_id, user_id=pm.player2_id
                ).all()
                if week_id
                else []
            )
        else:
            p1_sels, p2_sels = [], []
        eligible = get_oubliette_eligible_deck_ids(pm, p1_sels, p2_sels)
        data["oubliette_p1_eligible_deck_ids"] = eligible["p1"] if eligible else []
        data["oubliette_p2_eligible_deck_ids"] = eligible["p2"] if eligible else []
    else:
        data["oubliette_p1_eligible_deck_ids"] = None
        data["oubliette_p2_eligible_deck_ids"] = None

    exchange_borrows = getattr(pm, "exchange_borrows", [])
    data["exchange_borrows_count"] = len(exchange_borrows)
    data["exchange_borrows"] = (
        [
            {
                "borrowing_user_id": b.borrowing_user_id,
                "borrowed_deck_selection_id": b.borrowed_deck_selection_id,
            }
            for b in exchange_borrows
        ]
        if len(exchange_borrows) == 2
        else None
    )

    data["nordic_hexad_phase"] = getattr(pm, "nordic_hexad_phase", None)
    nordic_actions_raw = getattr(pm, "nordic_hexad_actions", [])
    current_phase = data["nordic_hexad_phase"] or 0
    # Reveal actions phase by phase — only show actions for phases already completed
    # (phase X is complete when current_phase > X)
    revealed_actions = [
        {
            "player_id": a.player_id,
            "phase": a.phase,
            "target_deck_selection_id": a.target_deck_selection_id,
        }
        for a in nordic_actions_raw
        if current_phase > a.phase
    ]
    data["nordic_hexad_actions"] = revealed_actions
    # Count actions submitted for the current (unrevealed) phase so the UI can show
    # "one player has submitted, waiting for the other" without leaking what was chosen
    if current_phase in (1, 2, 3):
        data["nordic_hexad_pending_phase_count"] = sum(
            1 for a in nordic_actions_raw if a.phase == current_phase
        )
    else:
        data["nordic_hexad_pending_phase_count"] = 0
    # After phase 3 (current_phase == 4), compute remaining deck IDs
    if current_phase >= 4:
        from keytracker.match_helpers import get_nordic_remaining_deck_ids

        remaining = get_nordic_remaining_deck_ids(pm)
        if remaining:
            data["nordic_p1_remaining_deck_ids"] = list(
                remaining.get(pm.player1_id, set())
            )
            data["nordic_p2_remaining_deck_ids"] = list(
                remaining.get(pm.player2_id, set())
            )
        else:
            data["nordic_p1_remaining_deck_ids"] = None
            data["nordic_p2_remaining_deck_ids"] = None
    else:
        data["nordic_p1_remaining_deck_ids"] = None
        data["nordic_p2_remaining_deck_ids"] = None

    # Moirai: reveal assignments only after both players have submitted all 3 (total 6)
    moirai_assignments_raw = getattr(pm, "moirai_assignments", [])
    data["moirai_assignments_count"] = len(moirai_assignments_raw)
    if len(moirai_assignments_raw) == 6:
        data["moirai_assignments"] = [
            {
                "assigning_user_id": a.assigning_user_id,
                "game_number": a.game_number,
                "assigned_deck_selection_id": a.assigned_deck_selection_id,
            }
            for a in moirai_assignments_raw
        ]
    else:
        data["moirai_assignments"] = None

    # Tertiate: reveal purge choices only after both players have submitted
    tertiate_purges_raw = getattr(pm, "tertiate_purge_choices", [])
    data["tertiate_purge_choices_count"] = len(tertiate_purges_raw)
    data["tertiate_purge_choices"] = (
        [
            {
                "choosing_user_id": p.choosing_user_id,
                "purged_house": p.purged_house,
            }
            for p in tertiate_purges_raw
        ]
        if len(tertiate_purges_raw) == 2
        else []
    )

    return data


def serialize_sealed_pool_entry(spd: SealedPoolDeck) -> dict:
    d = serialize_deck_summary(spd.deck) if spd.deck else None
    if d is not None:
        tokens = [
            c for c in spd.deck.cards_from_assoc if c.card_type == "Token Creature"
        ]
        d["token_name"] = tokens[0].card_title if tokens else None
    return {"id": spd.id, "deck": d}


def serialize_alliance_selection(sel: AlliancePodSelection) -> dict:
    return {
        "id": sel.id,
        "user_id": sel.user_id,
        "deck_id": sel.deck_id,
        "deck_name": sel.deck.name if sel.deck else None,
        "house_name": sel.house_name,
        "slot_type": sel.slot_type,
        "slot_number": sel.slot_number,
        "deck": serialize_deck_brief(sel.deck) if sel.deck else None,
    }


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


def serialize_standalone_match(match: StandaloneMatch, current_user_id=None) -> dict:
    creator_selections = (
        PlayerDeckSelection.query.filter_by(
            standalone_match_id=match.id, user_id=match.creator_id
        )
        .order_by(PlayerDeckSelection.slot_number)
        .all()
    )

    opponent_selections = []
    creator_pods = []
    opponent_pods = []
    if match.opponent_id:
        opponent_selections = (
            PlayerDeckSelection.query.filter_by(
                standalone_match_id=match.id, user_id=match.opponent_id
            )
            .order_by(PlayerDeckSelection.slot_number)
            .all()
        )

        creator_pods = AlliancePodSelection.query.filter_by(
            standalone_match_id=match.id, user_id=match.creator_id
        ).all()
        opponent_pods = AlliancePodSelection.query.filter_by(
            standalone_match_id=match.id, user_id=match.opponent_id
        ).all()

    return {
        "id": match.id,
        "uuid": match.uuid,
        "creator": serialize_user_brief(match.creator),
        "opponent": serialize_user_brief(match.opponent) if match.opponent else None,
        "format_type": match.format_type.value,
        "status": match.status.value,
        "best_of_n": match.best_of_n,
        "is_public": match.is_public,
        "max_sas": match.max_sas,
        "sas_floor": match.sas_floor,
        "combined_max_sas": match.combined_max_sas,
        "set_diversity": match.set_diversity,
        "house_diversity": match.house_diversity,
        "decks_per_player": match.decks_per_player,
        "sealed_pools_generated": match.sealed_pools_generated,
        "no_keycheat": match.no_keycheat,
        "allowed_sets": match.allowed_sets,
        "created_at": match.created_at.isoformat() + "Z" if match.created_at else None,
        "matchup": serialize_player_matchup(match.matchup) if match.matchup else None,
        "creator_selections": [serialize_deck_selection(s) for s in creator_selections],
        "opponent_selections": [
            serialize_deck_selection(s) for s in opponent_selections
        ],
        "creator_pods": [serialize_alliance_selection(p) for p in creator_pods],
        "opponent_pods": [serialize_alliance_selection(p) for p in opponent_pods],
        "alliance_restricted_list_version": (
            serialize_restricted_list_version(match.alliance_restricted_list_version)
            if getattr(match, "alliance_restricted_list_version_id", None)
            and match.alliance_restricted_list_version
            else None
        ),
    }


def serialize_admin_log_entry(entry: LeagueAdminLog) -> dict:
    return {
        "id": entry.id,
        "league_id": entry.league_id,
        "week_id": entry.week_id,
        "user": serialize_user_brief(entry.user),
        "action_type": entry.action_type,
        "details": entry.details,
        "created_at": entry.created_at.isoformat() + "Z" if entry.created_at else None,
    }


def serialize_deck_entry_log_entry(entry) -> dict:
    week = entry.week
    week_name = (week.name or f"Week {week.week_number}") if week else None
    return {
        "id": entry.id,
        "week_id": entry.week_id,
        "week_name": week_name,
        "target_user": serialize_user_brief(entry.target_user),
        "changed_by": serialize_user_brief(entry.changed_by),
        "action": entry.action,
        "deck_name": entry.deck_name,
        "deck_kf_id": entry.deck_kf_id,
        "slot_number": entry.slot_number,
        "created_at": entry.created_at.isoformat() + "Z" if entry.created_at else None,
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
        "game_id": game.game_id,
        "created_at": game.created_at.isoformat() + "Z" if game.created_at else None,
    }


def serialize_auction_bid(bid) -> dict:
    return {
        "user_id": bid.user_id,
        "username": bid.user.username if bid.user else None,
        "chains": bid.chains,
    }


def serialize_auction_deck(adeck, reveal_decks=False) -> dict:
    has_submitted = adeck.deck_id is not None
    show_deck = reveal_decks or adeck.assigned_to_user_id is not None
    return {
        "id": adeck.id,
        "brought_by_user_id": adeck.brought_by_user_id,
        "has_submitted": has_submitted,
        "deck": serialize_deck_summary(adeck.deck) if (show_deck and adeck.deck) else None,
        "assigned_to_user_id": adeck.assigned_to_user_id,
        "chains_bid": adeck.chains_bid,
        "bids": [serialize_auction_bid(b) for b in (adeck.bids or [])],
    }


def serialize_auction_detail(auction, viewer_id=None) -> dict:
    from keytracker.schema import AuctionStatus

    status = auction.status
    participant_ids = {p.user_id for p in auction.participants}
    viewer_has_submitted = False
    if viewer_id and viewer_id in participant_ids:
        my_deck = next(
            (d for d in auction.decks if d.brought_by_user_id == viewer_id), None
        )
        viewer_has_submitted = my_deck is not None and my_deck.deck_id is not None

    reveal_decks = status in (AuctionStatus.AUCTION, AuctionStatus.COMPLETED) or viewer_has_submitted

    # current_picker_id
    assigned_ids = {d.assigned_to_user_id for d in auction.decks if d.assigned_to_user_id}
    order = auction.player_order or [p.user_id for p in auction.participants]
    current_picker_id = None
    for uid in order:
        if uid not in assigned_ids:
            current_picker_id = uid
            break

    # current_bidder_id
    current_bidder_id = None
    if auction.active_deck_id:
        active_deck = next(
            (d for d in auction.decks if d.id == auction.active_deck_id), None
        )
        if active_deck:
            bid_user_ids = {b.user_id for b in active_deck.bids}
            for uid in order:
                if uid == current_picker_id:
                    continue
                if uid not in bid_user_ids:
                    current_bidder_id = uid
                    break

    # active_deck_bids
    active_deck_bids = []
    if auction.active_deck_id:
        active_deck = next(
            (d for d in auction.decks if d.id == auction.active_deck_id), None
        )
        if active_deck:
            active_deck_bids = [serialize_auction_bid(b) for b in active_deck.bids]

    participants_out = []
    for p in auction.participants:
        my_deck = next(
            (d for d in auction.decks if d.brought_by_user_id == p.user_id), None
        )
        participants_out.append(
            {
                "user_id": p.user_id,
                "username": p.user.username if p.user else None,
                "has_submitted": my_deck is not None and my_deck.deck_id is not None,
            }
        )

    return {
        "id": auction.id,
        "status": status.value,
        "creator_id": auction.creator_id,
        "passphrase": auction.passphrase if viewer_id == auction.creator_id else None,
        "player_order": order,
        "participants": participants_out,
        "decks": [serialize_auction_deck(d, reveal_decks=reveal_decks) for d in auction.decks],
        "active_deck_id": auction.active_deck_id,
        "active_deck_bids": active_deck_bids,
        "current_picker_id": current_picker_id,
        "current_bidder_id": current_bidder_id,
    }
