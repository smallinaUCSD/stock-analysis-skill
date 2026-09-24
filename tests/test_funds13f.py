from stockskill.data.funds13f import _name_key, diff, parse_info_table

XML = """<?xml version="1.0"?><informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><cusip>037833100</cusip><value>600</value>
<shrsOrPrnAmt><sshPrnamt>3</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><cusip>037833100</cusip><value>400</value>
<shrsOrPrnAmt><sshPrnamt>2</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><cusip>037833100</cusip><value>50</value>
<shrsOrPrnAmt><sshPrnamt>1</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt><putCall>Put</putCall></infoTable>
<infoTable><nameOfIssuer>ALLY FINL INC</nameOfIssuer><cusip>02005N100</cusip><value>100</value>
<shrsOrPrnAmt><sshPrnamt>10</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
</informationTable>"""


def test_parse_info_table_sums_rows_and_splits_options():
    h = parse_info_table(XML)
    assert h["037833100"]["value"] == 1000 and h["037833100"]["shares"] == 5
    assert h["037833100:PUT"]["put_call"] == "PUT"
    assert h["02005N100"]["name"] == "ALLY FINL INC"


def test_diff_labels_new_added_trimmed_sold():
    cur = {"A": {"cusip": "A", "name": "A", "value": 600.0, "shares": 150.0},
           "B": {"cusip": "B", "name": "B", "value": 300.0, "shares": 50.0},
           "C": {"cusip": "C", "name": "C", "value": 100.0, "shares": 10.0}}
    prev = {"A": {"cusip": "A", "name": "A", "value": 500.0, "shares": 100.0},
            "B": {"cusip": "B", "name": "B", "value": 400.0, "shares": 80.0},
            "D": {"cusip": "D", "name": "D", "value": 90.0, "shares": 9.0}}
    rows = {r["key"]: r for r in diff(cur, prev)}
    assert rows["A"]["change"] == "Added" and rows["A"]["share_change"] == 0.5
    assert rows["B"]["change"] == "Trimmed" and rows["C"]["change"] == "New"
    assert rows["D"]["change"] == "Sold out" and rows["D"]["prev_value"] == 90.0
    assert rows["A"]["weight"] == 0.6


def test_name_key_normalizes_abbreviations():
    assert _name_key("ALLY FINL INC") == _name_key("Ally Financial Inc.")
    assert _name_key("CHUBB LIMITED") == _name_key("Chubb Ltd")
