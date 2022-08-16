from flask_sqlalchemy import SQLAlchemy
import datetime
import enum


db = SQLAlchemy()


class House(enum.Enum):
    BROBNAR = "Brobnar"
    DIS = "Dis"
    EKWIDON = "Ekwidon"
    LOGOS = "Logos"
    MARS = "Mars"
    SANCTUM = "Sanctum"
    SAURIAN = "Saurian"
    SHADOWS = "Shadows"
    STARALLIANCE = "Star Alliance"
    UNFATHOMABLE = "Unfathomable"
    UNTAMED = "Untamed"


class Expansion(enum.Enum):
    COTA = "Call of the Archons"
    AOA = "Age of Ascension"
    WC = "Worlds Collide"
    MM = "Mass Mutation"
    DT = "Dark Tidings"
    WOE = "Winds of Exchange"


class Game(db.Model):
    """
    This represents a game of KeyForge. It stores information about players and decks,
    along with some basic metadata.
    """
    __tablename__ = "tracker_game"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    crucible_game_id = db.Column(db.String(36))
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    turns = db.Column(db.Integer)
    winner = db.Column(db.String(100), index=True)
    winner_deck_id = db.Column(db.String(100), index=True)
    winner_deck_name = db.Column(db.String(100))
    winner_keys = db.Column(db.Integer)
    winner_checks = db.Column(db.Integer)
    winner_deck_expansion = db.Column(db.Enum(Expansion))
    winner_upgrades_played = db.Column(db.Integer)
    winner_actions_played = db.Column(db.Integer)
    winner_creatures_played = db.Column(db.Integer)
    winner_artifacts_played = db.Column(db.Integer)
    winner_aember_reap_gained = db.Column(db.Integer)
    winner_aember_pips_gained = db.Column(db.Integer)
    winner_chains_gained = db.Column(db.Integer)
    winner_chains_starting = db.Column(db.Integer)
    winner_aember_captured = db.Column(db.Integer)
    winner_total_aember_gained = db.Column(db.Integer)
    winner_cards_archived = db.Column(db.Integer)
    winner_cards_drawn = db.Column(db.Integer)
    winner_cards_discarded = db.Column(db.Integer)
    winner_did_mulligan = db.Column(db.Boolean)
    loser = db.Column(db.String(100), index=True)
    loser_deck_id = db.Column(db.String(100), index=True)
    loser_deck_name = db.Column(db.String(100))
    loser_keys = db.Column(db.Integer)
    loser_checks = db.Column(db.Integer)
    loser_deck_expansion = db.Column(db.Enum(Expansion))
    loser_upgrades_played = db.Column(db.Integer)
    loser_actions_played = db.Column(db.Integer)
    loser_creatures_played = db.Column(db.Integer)
    loser_artifacts_played = db.Column(db.Integer)
    loser_aember_reap_gained = db.Column(db.Integer)
    loser_aember_pips_gained = db.Column(db.Integer)
    loser_chains_gained = db.Column(db.Integer)
    loser_chains_starting = db.Column(db.Integer)
    loser_aember_captured = db.Column(db.Integer)
    loser_total_aember_gained = db.Column(db.Integer)
    loser_cards_archived = db.Column(db.Integer)
    loser_cards_drawn = db.Column(db.Integer)
    loser_cards_discarded = db.Column(db.Integer)
    loser_did_mulligan = db.Column(db.Boolean)
    house_turn_counts = db.relationship("HouseTurnCounts", back_populates="game")
    turns = db.relationship("TurnState", back_populates="game")
    logs = db.relationship("Log", back_populates="game")


class HouseTurnCounts(db.Model):
    """
    This is a breakout table to avoid having to have two columns x the number of houses
    on Game. In a pinch we should be able to use AS to generate per-house columns on
    query results, but I think that's a pretty weird situation.
    """
    __tablename__ = "tracker_house_turn_counts"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.Integer, db.ForeignKey(Game.__table__.c.id), primary_key=True, index=True)
    game = db.relationship("Game", back_populates="house_turn_counts")
    winner = db.Column(db.Boolean)
    house = db.Column(db.Enum(House))
    turns = db.Column(db.Integer)


class TurnState(db.Model):
    """
    Each record here represents a summary of game state at the beginning of a player's
    turn. It mostly mimics the "turns" member from a game.json, but leaves out
    "activePlayer" because that makes no sense, and will count turn as an int - we
    should be able to order by id without problems.
    """
    __tablename__ = "tracker_turn_state"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.Integer, db.ForeignKey(Game.__table__.c.id), primary_key=True, index=True)
    game = db.relationship("Game", back_populates="turns")
    turn = db.Column(db.Integer)
    is_player_one = db.Column(db.Integer)
    player = db.Column(db.String(100))
    aember = db.Column(db.Integer)
    red_key = db.Column(db.Boolean)
    blue_key = db.Column(db.Boolean)
    yellow_key = db.Column(db.Boolean)


class Log(db.Model):
    """
    This represents the full log of game activity. I suspect this should actually
    be one record per event (log line), ordered by timestamps and deduplicated at
    display time if we have the same log from each player's perspective.
    """
    __tablename__ = "tracker_log"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.Integer, db.ForeignKey(Game.__table__.c.id), primary_key=True, index=True)
    game = db.relationship("Game", back_populates="logs")
    message = db.Column(db.String(1000))
    time = db.Column(db.DateTime)
    winner_perspective = db.Column(db.Boolean)

    def __repr__(self) -> str:
        if len(self.message) > 25:
            msg = self.message[:25] + "..."
        else:
            msg = self.message
        return f"<Log(game_id={self.game_id}, message='{msg}', time={self.time}, winner_perspective={self.winner_perspective})>"
