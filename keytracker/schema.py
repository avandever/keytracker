from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import (
    or_,
    select,
    types as sqlalchemy_types,
)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import column_property, mapped_column
from sqlalchemy.sql import func
import datetime
import enum
from collections import namedtuple
from typing import List
import copy
import xml.etree.ElementTree as ET
import json
from lingua import Language


db = SQLAlchemy()


# Changing order will break enum in db. Can add to end, but don't subtract or move
POSSIBLE_LANGUAGES = [
    Language.CHINESE,
    Language.ENGLISH,
    Language.FRENCH,
    Language.GERMAN,
    Language.ITALIAN,
    Language.KOREAN,
    Language.POLISH,
    Language.PORTUGUESE,
    Language.RUSSIAN,
    Language.SPANISH,
    Language.THAI,
    Language.VIETNAMESE,
]


Language = enum.Enum("Language", [l.name for l in POSSIBLE_LANGUAGES])


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
    THETIDE = "The Tide"
    GEISTOID = "Geistoid"
    KEYRAKEN = "Keyraken"
    # Special marker for platonic cards that don't have a house to call home, e.g.
    # anomalies, revenants, DAV, and It's Coming
    NONE = "No House"
    ELDERS = "Elders"


house_str_to_enum = {h.value: h for h in House.__members__.values()}


class CardType(enum.Enum):
    ACTION = "Action"
    CREATURE = "Creature"
    UPGRADE = "Upgrade"
    ARTIFACT = "Artifact"
    CREATURE2 = "Creature2"
    THETIDE = "The Tide"
    TOKEN_CREATURE = "Token Creature"


card_type_str_to_enum = {ct.value: ct for ct in CardType.__members__.values()}


class Expansion(enum.Enum):
    COTA = "Call of the Archons"
    AOA = "Age of Ascension"
    WC = "Worlds Collide"
    MM = "Mass Mutation"
    DT = "Dark Tidings"
    WOE = "Winds of Exchange"
    VM23 = "Vault Masters 2023"
    UC22 = "Unchained 2022"
    GR = "Grim Reminders"
    M24 = "Menagerie 2024"
    VM24 = "Vault Masters 2024"
    MCW = "Martian Civil War"


class Rarity(enum.Enum):
    COMMON = "Common"
    UNCOMMON = "Uncommon"
    RARE = "Rare"
    FIXED = "FIXED"
    VARIANT = "Variant"
    THETIDE = "The Tide"
    SPECIAL = "Special"
    EVILTWIN = "Evil Twin"
    TOKEN = "Token"


rarity_str_to_enum = {r.value: r for r in Rarity.__members__.values()}


ExpansionValues = namedtuple(
    "ExpansionValues", ["name", "shortname", "dokname", "number"]
)


EXPANSION_VALUES = [
    ExpansionValues("Call of the Archons", "CotA", "COTA", 341),
    ExpansionValues("Age of Ascension", "AoA", "AOA", 435),
    ExpansionValues("Worlds Collide", "WC", "WC", 452),
    ExpansionValues("Mass Mutation", "MM", "MM", 479),
    ExpansionValues("Dark Tidings", "DT", "DT", 496),
    ExpansionValues("Winds of Exchange", "WoE", "WoE", 600),
    ExpansionValues("Unchained 2022", "UC22", "UC22", 601),
    ExpansionValues("Vault Masters 2023", "VM23", "VM23", 609),
    ExpansionValues("Grim Reminders", "GR", "GR", 700),
    ExpansionValues("Menagerie 2024", "M24", "M24", 722),
    ExpansionValues("Vault Masters 2024", "VM24", "VM24", 737),
    ExpansionValues("Martian Civil War", "MCW", "MCW", 892),
]

EXPANSION_ID_TO_ABBR = {exp.number: exp.shortname for exp in EXPANSION_VALUES}


class KeyforgeSet(db.Model):
    __tablename__ = "tracker_set"
    number = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    shortname = db.Column(db.String(10), nullable=False)
    dokname = db.Column(db.String(10), nullable=False)


class KeyforgeRarity(db.Model):
    __tablename__ = "tracker_rarity"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(20), nullable=False, index=True)


class KeyforgeCardType(db.Model):
    __tablename__ = "tracker_card_type"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(20), nullable=False, index=True)


class KeyforgeHouse(db.Model):
    __tablename__ = "tracker_house"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(30), nullable=False, index=True)


class DeckLanguage(db.Model):
    __tablename__ = "tracker_deck_language"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False, index=True)


class GlobalVariable(db.Model):
    __tablename__ = "tracker_global_variable"
    name = db.Column(db.String(100), primary_key=True)
    value_str = db.Column(db.String(255), nullable=True)
    value_int = db.Column(db.Integer, nullable=True)


class Card(db.Model):
    __tablename__ = "tracker_card"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    kf_id = db.Column(db.String(36), index=True)
    card_title = db.Column(db.String(64))
    house = db.Column(db.String(20))
    card_type = db.Column(db.String(20))
    front_image = db.Column(db.String(256))
    card_text = db.Column(db.String(512))
    traits = db.Column(db.String(64))
    amber = db.Column(db.Integer)
    power = db.Column(db.Integer)
    armor = db.Column(db.Integer)
    rarity = db.Column(db.String(10))
    flavor_text = db.Column(db.String(512))
    card_number = db.Column(db.String(10))
    expansion = db.Column(db.Integer)
    is_maverick = db.Column(db.Boolean)
    is_anomaly = db.Column(db.Boolean)
    is_enhanced = db.Column(db.Boolean)
    is_non_deck = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<Card({self.card_title}, {self.house})>"


CARD_ATTRS = [
    "id",
    "kf_id",
    "card_title",
    "house",
    "card_type",
    "front_image",
    "card_text",
    "traits",
    "amber",
    "power",
    "armor",
    "rarity",
    "flavor_text",
    "card_number",
    "expansion",
    "is_maverick",
    "is_anomaly",
    "is_enhanced",
    "is_non_deck",
]


class EnhancedCard:
    def __init__(
        self,
        card: Card,
        amber: int = 0,
        capture: int = 0,
        draw: int = 0,
        damage: int = 0,
        discard: int = 0,
    ):
        for attr in CARD_ATTRS:
            setattr(self, attr, getattr(card, attr))
        self.enhanced_amber = amber
        self.enhanced_capture = capture
        self.enhanced_draw = draw
        self.enhanced_damage = damage
        self.enhanced_discard = discard


class Deck(db.Model):
    """
    This represents a deck, including various stats about it from the Master
    Vault. This object does not inherently contain a list of cards, however, and instead
    holds a list of ids that point to cards
    """

    __tablename__ = "tracker_deck"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    kf_id = db.Column(db.String(36), index=True, nullable=False)
    name = db.Column(db.String(256))
    expansion = db.Column(db.Integer)
    sas_rating = db.Column(db.Integer)
    aerc_score = db.Column(db.Integer)
    sas_version = db.Column(db.Integer)
    card_id_list = db.Column(db.String(259))
    dok: db.Mapped["DokDeck"] = db.relationship("DokDeck", back_populates="deck")
    enhancements = db.relationship("Enhancements", back_populates="deck")
    cards_from_assoc = db.relationship("CardInDeck", back_populates="deck")
    pod_stats = db.relationship("PodStats", back_populates="deck")
    language = db.Column(db.Enum(Language))

    def as_xml(self) -> str:
        deck = ET.Element("deck")
        kf_id = ET.SubElement(deck, "id")
        kf_id.text = self.kf_id
        name = ET.SubElement(deck, "name")
        name.text = self.name
        expansion = ET.SubElement(deck, "expansion")
        expansion.text = EXPANSION_ID_TO_ABBR[self.expansion]
        sas_rating = ET.SubElement(deck, "sas_rating")
        sas_rating.text = str(getattr(self.dok, "sas_rating", "UNKNOWN"))
        aerc_score = ET.SubElement(deck, "aerc_score")
        aerc_score.text = str(getattr(self.dok, "aerc_score", "UNKNOWN"))
        return ET.tostring(deck)

    def as_json(self) -> str:
        return json.dumps(
            {
                "id": self.kf_id,
                "name": self.name,
                "expansion": EXPANSION_ID_TO_ABBR[self.expansion],
                "sas_rating": getattr(self.dok, "sas_rating", "UNKNOWN"),
                "aerc_score": getattr(self.dok, "aerc_score", "UNKNOWN"),
                "houses": sorted([ps.house.value for ps in self.pod_stats]),
            }
        )

    @property
    def mv_url(self) -> str:
        return "https://www.keyforgegame.com/deck-details/" + self.kf_id

    @property
    def dok_url(self) -> str:
        return "https://decksofkeyforge.com/decks/" + self.kf_id

    def __repr__(self) -> str:
        return f'<Deck("{self.name}", {self.expansion},  {self.dok_url})>'


class PodStats(db.Model):
    __tablename__ = "tracker_pod_stats"
    deck_id = db.Column(
        db.Integer, db.ForeignKey(Deck.__table__.c.id), primary_key=True
    )
    house = db.Column(db.Enum(House), primary_key=True)
    deck = db.relationship("Deck", back_populates="pod_stats")
    enhanced_amber = db.Column(db.Integer, default=0)
    enhanced_capture = db.Column(db.Integer, default=0)
    enhanced_draw = db.Column(db.Integer, default=0)
    enhanced_damage = db.Column(db.Integer, default=0)
    enhanced_discard = db.Column(db.Integer, default=0)
    # not derived because should be indexable
    num_enhancements = db.Column(db.Integer, default=0, index=True)
    aerc_score = db.Column(db.Integer, default=0, index=True)
    sas_rating = db.Column(db.Integer, default=0, index=True)
    num_mutants = db.Column(db.Integer, default=0)
    creatures = db.Column(db.Integer, default=0)
    raw_amber = db.Column(db.Integer, default=0)
    total_amber = db.Column(db.Integer, default=0)

    def __repr__(self) -> str:
        msg = f"<PodStats(D: {self.deck_id}, h: {self.house}, "
        msg += f"e:{self.num_enhancements}"
        msg += f" a:{self.enhanced_amber} c:{self.enhanced_capture}"
        msg += f" f:{self.enhanced_draw} d:{self.enhanced_damage}"
        msg += f" m:{self.num_mutants}"
        msg += ")>"
        return msg


class Enhancements(db.Model):
    __tablename__ = "tracker_enhancements"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    card_id = db.Column(db.Integer, db.ForeignKey(Card.__table__.c.id))
    card = db.relationship("Card")
    deck_id = db.Column(db.Integer, db.ForeignKey(Deck.__table__.c.id))
    deck = db.relationship("Deck", back_populates="enhancements")
    amber = db.Column(db.Integer, default=0)
    capture = db.Column(db.Integer, default=0)
    draw = db.Column(db.Integer, default=0)
    damage = db.Column(db.Integer, default=0)
    discard = db.Column(db.Integer, default=0)


platonic_card_traits = db.Table(
    "tracker_platonic_card_traits",
    db.metadata,
    db.Column(
        "platonic_card_id", db.ForeignKey("tracker_platonic_card.id"), primary_key=True
    ),
    db.Column("trait_id", db.ForeignKey("tracker_traits.id"), primary_key=True),
)


class Trait(db.Model):
    __tablename__ = "tracker_traits"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(24))

    def __repr__(self) -> str:
        return f"<Trait({self.name})>"


class PlatonicCard(db.Model):
    """
    "Ideal" version of a card, without respect to snoozy real life materialization
    details like house membership or enhancements
    """

    __tablename__ = "tracker_platonic_card"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    card_title = db.Column(db.String(64))
    card_type = db.Column(db.Enum(CardType))
    front_image = db.Column(db.String(100))
    card_text = db.Column(db.String(512))
    traits = db.relationship("Trait", secondary=platonic_card_traits)
    amber = db.Column(db.Integer)
    power = db.Column(db.Integer)
    armor = db.Column(db.Integer)
    flavor_text = db.Column(db.String(512))
    house = db.Column(db.Enum(House))
    expansions = db.relationship("PlatonicCardInSet", back_populates="card")
    is_non_deck = db.Column(db.Boolean, default=False)

    def __repr__(self) -> str:
        return f"<PlatonicCard({self.card_title})>"


class PlatonicCardInSet(db.Model):
    __tablename__ = "tracker_platonic_card_expansions"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    card_id = db.Column(
        db.Integer, db.ForeignKey(PlatonicCard.__table__.c.id), index=True
    )
    card = db.relationship("PlatonicCard", back_populates="expansions")
    card_kf_id = db.Column(db.String(36))
    expansion = db.Column(db.Integer, primary_key=True)
    rarity = db.Column(db.Enum(Rarity))
    card_number = db.Column(db.String(10))
    is_anomaly = db.Column(db.Boolean, default=False)
    front_image = db.Column(db.String(100))
    # Every PlatonicCardInSet is either maverick or not, so actually it makes sense to
    # record house here. It can eventually be dropped from CardInDeck.
    house = db.Column(db.Enum(House))
    is_maverick = db.Column(db.Boolean, default=False)
    # And enhanced vs. non-enhanced are also different ids
    is_enhanced = db.Column(db.Boolean, default=False)
    card_title = association_proxy("card", "card_title")
    card_type = association_proxy("card", "card_type")
    card_text = association_proxy("card", "card_text")
    traits = association_proxy("card", "traits")
    amber = association_proxy("card", "amber")
    power = association_proxy("card", "power")
    armor = association_proxy("card", "armor")
    flavor_text = association_proxy("card", "flavor_text")
    is_non_deck = association_proxy("card", "is_non_deck")

    def __repr__(self) -> str:
        return f"<PlatonicCardInSet({self.card.card_title}, {self.expansion})>"


class CardInDeck(db.Model):
    """
    This represents a card in a deck. Thus, a deck with 3 CTW would have 3 of these with
    the platonic_card_id of the platonic CTW. Because there will be 36-37 of these per
    deck (approaching 3 million at time of writing, meaning over 100 million rows in
    this table), it's nice to keep it compact. So, Integer and Boolean only, please.
    In fact, this means that we don't keep track here of which uuid in particular is
    associated with this particular card in the MV. Basic math here: 7 Integer * 4B =
    28B; 1 bool = 1B; 1 enum = 1B (because few values) = 30 bytes, whereas the UUID
    would be 37 bytes on its own, more than doubling storage size for little to no
    benefit. If we really ever need that, we have deck.card_id_list. But we can already
    expect that every million decks will add 1GB to this table, not accounting for
    indices.

    In fact, 3GB may make us wonder if we really need this table - is it worth the
    trouble? BUT if we ever want search on this stuff, like find a deck that has two
    Mark of Dis that each have an extra amber on them, then yes, this is necessary.
    """

    __tablename__ = "tracker_card_in_deck"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    platonic_card_id = db.Column(
        db.Integer,
        db.ForeignKey(PlatonicCard.__table__.c.id),
        index=True,
    )
    platonic_card = db.relationship("PlatonicCard")
    card_in_set_id = db.Column(
        db.Integer,
        db.ForeignKey(PlatonicCardInSet.__table__.c.id),
    )
    card_in_set = db.relationship("PlatonicCardInSet")
    deck_id = db.Column(
        db.Integer,
        db.ForeignKey(Deck.__table__.c.id),
        index=True,
    )
    deck = db.relationship("Deck", back_populates="cards_from_assoc")
    # TODO: replace with association proxy to card_in_set
    house = db.Column(db.Enum(House))
    # TODO: replace with association proxy to card_in_set
    is_enhanced = db.Column(db.Boolean, default=False)
    enhanced_amber = db.Column(db.Integer, default=0)
    enhanced_capture = db.Column(db.Integer, default=0)
    enhanced_draw = db.Column(db.Integer, default=0)
    enhanced_damage = db.Column(db.Integer, default=0)
    enhanced_discard = db.Column(db.Integer, default=0)
    card_title = association_proxy("platonic_card", "card_title")
    card_type = association_proxy("platonic_card", "card_type")
    card_text = association_proxy("platonic_card", "card_text")
    traits = association_proxy("platonic_card", "traits")
    amber = association_proxy("platonic_card", "amber")
    power = association_proxy("platonic_card", "power")
    armor = association_proxy("platonic_card", "armor")
    flavor_text = association_proxy("platonic_card", "flavor_text")
    is_non_deck = association_proxy("platonic_card", "is_non_deck")
    natural_house = association_proxy("platonic_card", "house")
    card_kf_id = association_proxy("card_in_set", "card_kf_id")
    front_image = association_proxy("card_in_set", "front_image")
    expansion = association_proxy("card_in_set", "expansion")
    rarity = association_proxy("card_in_set", "rarity")
    card_number = association_proxy("card_in_set", "card_number")
    is_anomaly = association_proxy("card_in_set", "is_anomaly")

    # TODO: replace with association proxy to card_in_set
    @hybrid_property
    def is_maverick(self):
        return (
            self.house != self.natural_house
            and not self.is_anomaly
        )

    def __repr__(self) -> str:
        return (
            f"<CardInDeck({self.card_title}, {self.house},"
            f"{self.enhanced_amber}a|{self.enhanced_capture}c|"
            f"{self.enhanced_draw}f|{self.enhanced_damage}d|"
            f"{self.enhanced_discard}D,{self.deck.dok_url})>"
        )


class DokDeck(db.Model):
    """
    This represents DOK data about a deck.
    """

    __tablename__ = "tracker_dok_deck"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deck_id: db.Mapped[int] = mapped_column(
        db.ForeignKey(Deck.__table__.c.id),
        primary_key=True,
    )
    deck: db.Mapped["Deck"] = db.relationship("Deck", back_populates="dok")
    sas_rating = db.Column(db.Float)
    synergy_rating = db.Column(db.Float)
    antisynergy_rating = db.Column(db.Float)
    aerc_score = db.Column(db.Float)
    amber_control = db.Column(db.Float)
    expected_amber = db.Column(db.Float)
    artifact_control = db.Column(db.Float)
    creature_control = db.Column(db.Float)
    efficiency = db.Column(db.Float)
    recursion = db.Column(db.Float)
    disruption = db.Column(db.Float)
    creature_protection = db.Column(db.Float)
    other = db.Column(db.Float)
    effective_power = db.Column(db.Float)
    raw_amber = db.Column(db.Integer)
    action_count = db.Column(db.Integer)
    upgrade_count = db.Column(db.Integer)
    creature_count = db.Column(db.Integer)
    last_refresh = db.Column(
        db.DateTime,
        default=func.now(),
        onupdate=func.utc_timestamp(),
    )

    def __repr__(self) -> str:
        return (
            "<DokDeck("
            f"id={self.id}, deck_id={self.deck.id}, "
            f"sas_rating={self.sas_rating}, aerc_score={self.aerc_score}"
            ")>"
        )


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
    first_player = db.Column(db.String(100))
    first_player_id = db.Column(db.Integer)
    winner = db.Column(db.String(100), index=True)
    winner_id = db.Column(db.Integer)
    winner_deck_dbid = db.Column(
        db.Integer,
        db.ForeignKey(Deck.__table__.c.id),
        index=True,
    )
    winner_deck = db.relationship("Deck", foreign_keys=winner_deck_dbid)
    winner_deck_id = db.Column(db.String(100))
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
    loser_id = db.Column(db.Integer)
    loser_deck_dbid = db.Column(
        db.Integer, db.ForeignKey(Deck.__table__.c.id), index=True
    )
    loser_deck = db.relationship("Deck", foreign_keys=[loser_deck_dbid])
    loser_deck_id = db.Column(db.String(100))
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
    winner_sas_rating = column_property(
        select(Deck.sas_rating)
        .where(Deck.id == winner_deck_dbid)
        .correlate_except(Deck)
        .scalar_subquery()
    )
    loser_sas_rating = column_property(
        select(Deck.sas_rating)
        .where(Deck.id == loser_deck_dbid)
        .correlate_except(Deck)
        .scalar_subquery()
    )
    combined_sas_rating = column_property(
        winner_sas_rating.expression + loser_sas_rating.expression
    )
    winner_aerc_score = column_property(
        select(Deck.aerc_score)
        .where(Deck.id == winner_deck_dbid)
        .correlate_except(Deck)
        .scalar_subquery()
    )
    loser_aerc_score = column_property(
        select(Deck.aerc_score)
        .where(Deck.id == loser_deck_dbid)
        .correlate_except(Deck)
        .scalar_subquery()
    )
    combined_aerc_score = column_property(
        winner_aerc_score.expression + loser_aerc_score.expression
    )

    @property
    def insist_first_player(self) -> str:
        return self.first_player or sorted([self.winner, self.loser])[0]


class Player(db.Model):
    """
    Represents a player. Primarily, this should save us some trouble by being able to
    use ids instead of strings in most tables.
    The anonymous field will not be used for display. Rather, it will cause any
    sightings of that username to be pointed at the "anonymous" player entry instead.
    Ironically, the "anonymous" user will have a false in the anonymous column.
    """

    __tablename__ = "tracker_player"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100))
    anonymous = db.Column(db.Boolean, default=False)

    def __repr__(self) -> str:
        return f"<Player({self.username})>"


class HouseTurnCounts(db.Model):
    """
    This is a breakout table to avoid having to have two columns x the number of houses
    on Game. In a pinch we should be able to use AS to generate per-house columns on
    query results, but I think that's a pretty weird situation.
    """

    __tablename__ = "tracker_house_turn_counts"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(
        db.Integer, db.ForeignKey(Game.__table__.c.id), primary_key=True, index=True
    )
    game = db.relationship("Game", back_populates="house_turn_counts")
    winner = db.Column(db.Boolean)
    player_id = db.Column(
        db.Integer, db.ForeignKey(Player.__table__.c.id), primary_key=True, index=True
    )
    player = db.relationship("Player")
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
    game_id = db.Column(
        db.Integer, db.ForeignKey(Game.__table__.c.id), primary_key=True, index=True
    )
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
    game_id = db.Column(db.Integer, db.ForeignKey(Game.__table__.c.id), index=True)
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


class User(UserMixin, db.Model):
    __tablename__ = "tracker_user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    name = db.Column(db.String(100))
