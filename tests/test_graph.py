from stockskill.data.graph import load_relationships, neighbors, short_name


def test_neighbors_splits_suppliers_customers_investments():
    rel = {"names": {"TSM": "TSMC", "OpenAI": "OpenAI (private)"},
           "edges": [{"from": "TSM", "to": "NVDA", "what": "foundry", "basis": "10-K"},
                     {"from": "NVDA", "to": "MSFT", "what": "GPUs", "basis": "reported"},
                     {"from": "MSFT", "to": "OpenAI", "what": "investor", "basis": "10-K", "kind": "invests"}]}
    n = neighbors("NVDA", rel)
    assert [x["ticker"] for x in n["suppliers"]] == ["TSM"] and n["suppliers"][0]["name"] == "TSMC"
    assert [x["ticker"] for x in n["customers"]] == ["MSFT"]
    m = neighbors("MSFT", rel)
    assert m["suppliers"][0]["ticker"] == "NVDA"
    assert m["investments"][0]["ticker"] is None and m["investments"][0]["name"] == "OpenAI (private)"


def test_curated_file_is_consistent():
    rel = load_relationships()
    assert len(rel["edges"]) > 40
    for e in rel["edges"]:
        assert e["from"] != e["to"] and e.get("what") and e.get("basis")


def test_short_name_for_filing_search():
    assert short_name("NVIDIA Corp") == "NVIDIA"
    assert short_name("Taiwan Semiconductor Manufacturing Co Ltd") == "Taiwan Semiconductor"
    assert short_name("Apple Inc.") == "Apple"


def test_extract_concentration_from_xbrl():
    from stockskill.data.customers import extract_concentration, short_label
    xml = b"""<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
  xmlns:us-gaap="http://fasb.org/us-gaap/2025">
 <xbrli:context id="c1"><xbrli:entity><xbrli:segment>
   <xbrldi:explicitMember dimension="srt:MajorCustomersAxis">nvda:CustomerOneMember</xbrldi:explicitMember>
   <xbrldi:explicitMember dimension="us-gaap:ConcentrationRiskByBenchmarkAxis">us-gaap:SalesRevenueNetMember</xbrldi:explicitMember>
 </xbrli:segment></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-27</xbrli:startDate><xbrli:endDate>2026-01-25</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="c2"><xbrli:entity><xbrli:segment>
   <xbrldi:explicitMember dimension="srt:MajorCustomersAxis">crwv:MicrosoftMember</xbrldi:explicitMember>
   <xbrldi:explicitMember dimension="us-gaap:ConcentrationRiskByBenchmarkAxis">us-gaap:RevenueFromContractWithCustomerMember</xbrldi:explicitMember>
 </xbrli:segment></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-27</xbrli:startDate><xbrli:endDate>2026-01-25</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="c3"><xbrli:entity><xbrli:segment>
   <xbrldi:explicitMember dimension="srt:MajorCustomersAxis">nvda:CustomerOneMember</xbrldi:explicitMember>
   <xbrldi:explicitMember dimension="us-gaap:ConcentrationRiskByBenchmarkAxis">us-gaap:AccountsReceivableMember</xbrldi:explicitMember>
 </xbrli:segment></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-27</xbrli:startDate><xbrli:endDate>2026-01-25</xbrli:endDate></xbrli:period></xbrli:context>
 <us-gaap:ConcentrationRiskPercentage1 contextRef="c1">0.22</us-gaap:ConcentrationRiskPercentage1>
 <us-gaap:ConcentrationRiskPercentage1 contextRef="c2">0.62</us-gaap:ConcentrationRiskPercentage1>
 <us-gaap:ConcentrationRiskPercentage1 contextRef="c3">0.25</us-gaap:ConcentrationRiskPercentage1>
</xbrli:xbrl>"""
    r = extract_concentration(xml)
    assert r["period_end"] == "2026-01-25"
    got = [(c["label"], c["pct"], c["anonymous"]) for c in r["customers"]]
    assert got == [("Microsoft", 0.62, False), ("Customer One", 0.22, True)]   # receivables share ignored
    assert short_label("Customer One") == "Cust 1" and short_label("Reseller A") == "Resl A"
