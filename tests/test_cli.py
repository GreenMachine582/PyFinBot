"""The report CLI (pyfinbot.cli): the same numbers and columns as the web's
CSV downloads and the API's JSON, against the test database."""
import csv
import io
import json

import pytest

from pyfinbot import cli

from .conftest import create_stock, web_login
from .test_reports import _seed_dividend
from .test_web_reports import _csv, _seed

USER_ID = "cli-user"


async def _cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = await cli.run(list(argv), stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def _rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


class TestReports:
    async def test_holdings_csv_matches_the_web_download(self, client, session):
        await web_login(client, USER_ID)
        await _seed(client, session)
        code, out, _ = await _cli("holdings", "--user", USER_ID, "--as-of", "2025-06-30")
        assert code == 0
        web = await client.get("/reports/holdings.csv", params={"as_of": "2025-06-30"})
        assert _rows(out) == _csv(web)
        assert _rows(out)[1][:4] == ["ASX", "BHP", "BHP Group", "150.0"]

    async def test_gains_csv_matches_the_web_download(self, client, session):
        await web_login(client, USER_ID)
        await _seed(client, session)
        code, out, _ = await _cli("gains", "--user", USER_ID, "--fy", "2024")
        assert code == 0
        assert _rows(out) == _csv(await client.get("/reports/gains.csv", params={"fy": "2024"}))
        assert float(_rows(out)[1][6]) == pytest.approx(740)

    async def test_dividends_json_matches_the_api(self, client, session):
        await web_login(client, USER_ID)
        await _seed(client, session)
        code, out, _ = await _cli("dividends", "--user", USER_ID, "--format", "json")
        assert code == 0
        body = json.loads(out)
        assert body["fy"] is None
        assert body["total_dividends_received"] == pytest.approx(300)
        assert body["items"][0]["units_held_at_ex_date"] == pytest.approx(200)

    async def test_dividends_fy_filter(self, client, session):
        await web_login(client, USER_ID)
        bhp = await _seed(client, session)
        await _seed_dividend(session, bhp["id"], "2025-09-01", "2.00")
        _, out, _ = await _cli("dividends", "--user", USER_ID, "--fy", "2025", "--format", "json")
        body = json.loads(out)
        assert body["fy"] == 2025
        assert [i["ex_date"] for i in body["items"]] == ["2025-09-01"]

    async def test_gains_defaults_to_the_current_fy(self, client):
        await web_login(client, USER_ID)
        _, out, _ = await _cli("gains", "--user", USER_ID, "--format", "json")
        from datetime import date

        from greentechhub_core.dates import fiscal_year
        assert json.loads(out)["fy"] == fiscal_year(date.today())

    async def test_holdings_default_to_today_and_can_be_empty(self, client):
        await web_login(client, USER_ID)
        await create_stock(client)
        code, out, _ = await _cli("holdings", "--user", USER_ID)
        assert code == 0
        assert _rows(out) == [["Market", "Symbol", "Name", "Units held", "Avg cost", "Cost base",
                               "Dividends received"]]


class TestOutput:
    async def test_output_file_gets_a_bom_like_the_web_download(self, client, session, tmp_path):
        await web_login(client, USER_ID)
        await _seed(client, session)
        path = tmp_path / "gains.csv"
        code, out, _ = await _cli("gains", "--user", USER_ID, "--fy", "2024", "-o", str(path))
        assert code == 0 and out == ""
        data = path.read_bytes()
        assert data.startswith(b"\xef\xbb\xbf")
        assert data == (await client.get("/reports/gains.csv", params={"fy": "2024"})).content

    async def test_json_output_file_has_no_bom(self, client, tmp_path):
        await web_login(client, USER_ID)
        path = tmp_path / "holdings.json"
        await _cli("holdings", "--user", USER_ID, "--format", "json", "--output", str(path))
        assert json.loads(path.read_text(encoding="utf-8"))["holdings"] == []


class TestErrors:
    async def test_unknown_user_exports_nothing(self, client, tmp_path):
        path = tmp_path / "out.csv"
        code, out, err = await _cli("holdings", "--user", "nobody", "-o", str(path))
        assert code == 1
        assert out == "" and not path.exists()
        assert "Nothing exported: no user 'nobody'." in err

    @pytest.mark.parametrize("argv", [
        [],                                          # no report
        ["holdings"],                                # no --user
        ["holdings", "--user", "u", "--format", "xml"],
        ["holdings", "--user", "u", "--as-of", "30/06/2025"],
        ["gains", "--user", "u", "--fy", "next"],
        ["bogus", "--user", "u"],
    ])
    async def test_bad_arguments_exit_with_usage(self, argv, capsys):
        with pytest.raises(SystemExit) as exc:
            await cli.run(argv)
        assert exc.value.code == 2
        assert "usage: pyfinbot" in capsys.readouterr().err
