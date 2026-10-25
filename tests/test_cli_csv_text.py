"""The CLI's CSV through greentechhub-core v0.16's exports.csv_text: no BOM
on stdout (it's piped), the same rows as the web download; -o files keep
theirs (test_cli.py's byte-for-byte check)."""
import csv
import io
from datetime import date

from greentechhub_core.exports import csv_text

from pyfinbot import cli
from pyfinbot.core import report_rows, reports

from .conftest import user_id, web_login
from .test_web_reports import _csv, _seed

USER = "cli-csv-text"


async def test_stdout_csv_has_no_bom_and_the_web_downloads_rows(gth_client, gth_session):
    await web_login(gth_client, USER)
    await _seed(gth_client, gth_session)
    out, err = io.StringIO(), io.StringIO()
    code = await cli.run(["gains", "--user", USER, "--fy", "2024"], stdout=out, stderr=err)
    assert code == 0, err.getvalue()
    text = out.getvalue()
    assert not text.startswith("﻿")
    web = await gth_client.get("/reports/gains.csv", params={"fy": "2024"})
    assert list(csv.reader(io.StringIO(text))) == _csv(web)


async def test_render_is_core_csv_text_without_a_bom(gth_client, gth_session):
    await web_login(gth_client, USER)
    await _seed(gth_client, gth_session)
    report = await reports.holdings_report(gth_session, await user_id(USER), date(2025, 6, 30))
    assert cli.render(report, "csv") == csv_text(report_rows.holdings_rows(report), bom=False)
