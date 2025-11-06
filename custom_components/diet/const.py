DOMAIN = "diet"
DB_FILENAME = "diet.sqlite"
CONF_FREE_MEALS_PER_WEEK = "free_meals_per_week"
CONF_FREE_LIMIT_MODE = "free_limit_mode" # "hard"|"soft"
DEFAULTS = {CONF_FREE_MEALS_PER_WEEK: 2, CONF_FREE_LIMIT_MODE: "soft"}
PLATFORMS = ["sensor"]
MEAL_TYPES = ("breakfast","lunch","dinner","snack_am","snack_pm")