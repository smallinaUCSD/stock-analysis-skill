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
