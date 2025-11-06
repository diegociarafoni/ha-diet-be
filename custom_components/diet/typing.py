from __future__ import annotations
from typing import Literal, TypedDict, NotRequired, List, Dict


# -----------------------------
# Literal types
# -----------------------------
MealType = Literal["breakfast", "lunch", "dinner", "snack_am", "snack_pm"]
ChoiceSource = Literal["proposed", "alternative", "free", "skipped"]


# -----------------------------
# Template DTO
# -----------------------------
class TemplateMealAlt(TypedDict):
    id: int
    title: str
    items: NotRequired[str]
    calories: NotRequired[int]


class TemplateMeal(TypedDict):
    id: int
    dow: int  # 0=Mon ... 6=Sun
    meal_type: MealType
    title: NotRequired[str]
    proposed_label: NotRequired[str]
    proposed_items: NotRequired[str]
    calories: NotRequired[int]
    required: bool
    default_source: Literal["proposed", "free", "skipped"]


# -----------------------------
# Day/Week DTO (WebSocket/API)
# -----------------------------
class ChosenInfo(TypedDict):
    source: ChoiceSource
    title: NotRequired[str]
    notes: NotRequired[str]
    ts: NotRequired[str]


class ProposedInfo(TypedDict, total=False):
    title: str
    items: NotRequired[str]
    calories: NotRequired[int]


class DayMeal(TypedDict, total=False):
    meal_type: MealType
    proposed: ProposedInfo | None
    alternatives: List[TemplateMealAlt]
    chosen: ChosenInfo | None


class SnacksState(TypedDict, total=False):
    am: Dict[str, object]  # {"done": bool, "ts"?: str}
    pm: Dict[str, object]


class DayData(TypedDict, total=False):
    date: str  # ISO YYYY-MM-DD
    hunger: NotRequired[int]  # 1..5
    notes: NotRequired[str]
    snacks: SnacksState
    meals: List[DayMeal]


class WeekResponse(TypedDict):
    start: str  # Monday ISO date
    days: List[DayData]


# -----------------------------
# Capabilities DTO
# -----------------------------
class CapabilityProfile(TypedDict):
    profile_id: int
    display_name: str
    can_read: bool
    can_write: bool


class CapabilitiesPayload(TypedDict):
    subject_profile_id: int | None
    profiles: List[CapabilityProfile]


# -----------------------------
# Next Meals (common view) DTO
# -----------------------------
class NextMeal(TypedDict):
    type: Literal["lunch", "dinner"]
    date: str
    title: str
    status: Literal["planned", "proposed", "alternative", "free", "skipped"]


class NextMealsPerProfile(TypedDict):
    profile_id: int
    display_name: NotRequired[str]
    upcoming: List[NextMeal]


class NextMealsPayload(TypedDict):
    now: str
    horizon: str
    profiles: List[NextMealsPerProfile]
