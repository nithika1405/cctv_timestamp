from src.query import QueryEngine, parse_time


def test_parse_time():
    assert parse_time("00:15") == 15.0
    assert parse_time("01:30") == 90.0
    assert parse_time("10") == 10.0


def test_query_engine():
    events = [
        {"id": 1, "timestamp_seconds": 5.0, "object_label": "person", "event_type": "person_entering"},
        {"id": 2, "timestamp_seconds": 15.0, "object_label": "backpack", "event_type": "placed"},
        {"id": 3, "timestamp_seconds": 30.0, "object_label": "backpack", "event_type": "unattended"},
        {"id": 4, "timestamp_seconds": 45.0, "object_label": "person", "event_type": "person_leaving"},
    ]

    engine = QueryEngine(events)

    # Keyword match + synonym mapping
    res = engine.query("when was the bag put down?")
    assert res["id"] == 2

    # Synonym mapping for "abandoned" -> "unattended"
    res2 = engine.query("was a bag abandoned?")
    assert res2["id"] == 3

    # Count mode
    res3 = engine.query("how many people entered or left?")
    assert res3["count"] == 2

    # Time constraint "after"
    res4 = engine.query("events after 00:20")
    # First event after 20 secs is ID 3 (unattended backpack)
    assert res4["id"] == 3

    # Time constraint "before"
    res5 = engine.query("bag before 00:20")
    # First bag event before 20 secs is ID 2 (placed)
    assert res5["id"] == 2

    # Time constraint "between"
    res6 = engine.query("between 10 and 40 seconds")
    # First match in that range is ID 2
    assert res6["id"] == 2


def test_query_engine_phase3_events():
    events = [
        {"id": 1, "timestamp_seconds": 5.0, "object_label": "person", "event_type": "person_entering"},
        {"id": 2, "timestamp_seconds": 12.0, "object_label": "person", "event_type": "zone_breach"},
        {"id": 3, "timestamp_seconds": 25.0, "object_label": "person", "event_type": "loitering"},
    ]
    engine = QueryEngine(events)

    res_breach = engine.query("who breached the restricted zone?")
    assert res_breach["id"] == 2

    res_loiter = engine.query("did someone loiter or linger?")
    assert res_loiter["id"] == 3
