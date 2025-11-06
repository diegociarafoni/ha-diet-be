import pytest


@pytest.mark.asyncio
async def test_schema_created(diet_db):
    db, _ = diet_db

    # meta con schema_version
    async with db.conn.execute("SELECT value FROM meta WHERE key='schema_version'") as c:
        row = await c.fetchone()
    assert row is not None, "meta.schema_version mancante"

    # tabelle chiave presenti
    tables = {
        "diet_profiles",
        "profile_acl",
        "week_templates",
        "template_meals",
        "template_meal_alternatives",
        "plan_days",
        "day_meals",
        "snacks",
        "free_meals",
        "swaps",
    }
    async with db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ) as c:
        names = {r[0] async for r in c}
    assert tables.issubset(names), f"Tabelle mancanti: {tables - names}"

    # colonna default_source su template_meals
    async with db.conn.execute("PRAGMA table_info(template_meals)") as c:
        cols = {r[1] async for r in c}
    assert "default_source" in cols, "Colonna default_source mancante su template_meals"
