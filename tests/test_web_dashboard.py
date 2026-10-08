"""The dashboard's summary tiles and largest holdings, seeded relative to
today's FY so the numbers don't go stale."""
from datetime import date, timedelta

from greentechhub_core.dates import fiscal_year, fiscal_year_bounds, fiscal_year_label

from .conftest import create_stock, web_login
from .test_reports import _seed_dividend
from .test_web_reports import _txn

FY = fiscal_year(date.today())
FY_START = fiscal_year_bounds(FY)[0]


def _day(offset: int) -> str:
    return (FY_START + timedelta(days=offset)).isoformat()


async def _seed(client, session):
    """BHP: buy 100 @ 40 and 100 @ 50 before this FY; on its first day a sell
    of 50 @ 60 less 10 fees (gain 2,990 - 50 × 45 = 740) and a 1.50 dividend
    on the 150 then held (225). CBA: 10 @ 100, a smaller holding."""
    bhp = await create_stock(client)
    cba = await create_stock(client, symbol="CBA", name="Commonwealth Bank")
    await _txn(client, bhp["id"], "Buy", "100", "40", _day(-30))
    await _txn(client, bhp["id"], "Buy", "100", "50", _day(-10))
    await _seed_dividend(session, bhp["id"], FY_START, "1.50")
    await _txn(client, bhp["id"], "Sell", "50", "60", _day(0), fees="10")
    await _txn(client, cba["id"], "Buy", "10", "100", _day(-5))


async def test_tiles_show_this_fy(client, session):
    await web_login(client, "web-dashboard")
    await _seed(client, session)
    page = (await client.get("/")).text
    assert "gth-stat-grid" in page
    assert f"Realised gain/loss, FY {fiscal_year_label(FY)}" in page
    assert "740.00" in page                    # realised gain
    assert "225.00" in page                    # dividends this FY
    assert "7,750.00" in page                  # cost base: 150 × 45 + 10 × 100
    assert "Coming soon" not in page


async def test_largest_holdings_first(client, session):
    await web_login(client, "web-dashboard")
    await _seed(client, session)
    page = (await client.get("/")).text
    assert "Largest holdings" in page
    assert page.index('title="BHP Group"') < page.index('title="Commonwealth Bank"')
    assert "6,750.00" in page and "1,000.00" in page


async def test_only_the_top_holdings_are_listed(client):
    from pyfinbot.web.routes.dashboard import TOP_HOLDINGS

    await web_login(client, "web-dashboard")
    for i in range(TOP_HOLDINGS + 1):
        stock = await create_stock(client, symbol=f"S{i}", name=f"Stock {i}")
        await _txn(client, stock["id"], "Buy", "1", str(10 + i), _day(-1))
    page = (await client.get("/")).text
    assert 'title="Stock 0"' not in page       # the cheapest drops off
    assert f'title="Stock {TOP_HOLDINGS}"' in page


async def test_new_user_gets_an_empty_state(client):
    await web_login(client, "web-dashboard-new")
    page = (await client.get("/")).text
    assert "hold any stocks yet." in page
    assert 'href="/import"' in page
    assert "Largest holdings" not in page


async def test_other_users_holdings_stay_out(client, session):
    await web_login(client, "web-dashboard")
    await _seed(client, session)
    await web_login(client, "web-dashboard-other")
    page = (await client.get("/")).text
    assert "BHP Group" not in page
    assert "hold any stocks yet." in page
