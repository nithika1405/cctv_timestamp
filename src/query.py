from __future__ import annotations

import re


def parse_time(match: str) -> float:
    """Parse 'MM:SS' or 'SS' into seconds."""
    parts = match.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return float(parts[0])


class QueryEngine:
    """Translates natural language questions into search filters over events."""

    LABEL_ALIASES = {
        "bag": "backpack",
        "mobile": "phone",
        "cell": "phone",
        "cellphone": "phone",
        "luggage": "box",
        "package": "box",
        "guy": "person",
        "man": "person",
        "woman": "person",
        "someone": "person",
    }

    EVENT_ALIASES = {
        "left behind": "unattended",
        "abandoned": "unattended",
        "dropped": "placed",
        "put down": "placed",
        "picked": "picked_up",
        "took": "picked_up",
        "grabbed": "picked_up",
        "entered zone": "zone_entry",
        "zone entry": "zone_entry",
        "zone breach": "zone_breach",
        "breach": "zone_breach",
        "breached": "zone_breach",
        "trespass": "zone_breach",
        "trespassed": "zone_breach",
        "restricted": "zone_breach",
        "unauthorized": "zone_breach",
        "loitering": "loitering",
        "loiter": "loitering",
        "lingering": "loitering",
        "lingered": "loitering",
        "dwell": "loitering",
        "dwelling": "loitering",
        "stayed long": "loitering",
        "entered": "person_entering",
        "arrived": "person_entering",
        "left": "person_leaving",
        "departed": "person_leaving",
    }

    def __init__(self, events: list[dict]) -> None:
        self.events = events

    def query(self, question: str) -> dict | list[dict] | None:
        text = question.lower()
        if not text.strip() or not self.events:
            return None

        # Determine if the user is asking for a count
        is_count = "how many" in text or "count" in text

        # Determine sorting constraint (latest vs first)
        sort_descending = "last" in text or "latest" in text

        # Parse object labels
        target_labels = set()
        for word in text.split():
            clean_word = re.sub(r"[^\w]", "", word)
            if clean_word in ["backpack", "bottle", "phone", "box", "person"]:
                target_labels.add(clean_word)
            elif clean_word in self.LABEL_ALIASES:
                target_labels.add(self.LABEL_ALIASES[clean_word])

        # Parse event types
        target_events = set()
        for phrase, event_type in self.EVENT_ALIASES.items():
            if phrase in text:
                target_events.add(event_type)
        if "unattended" in text:
            target_events.add("unattended")
        if "placed" in text:
            target_events.add("placed")
        if "loitering" in text or "loiter" in text:
            target_events.add("loitering")
        if "breach" in text:
            target_events.add("zone_breach")
        if "zone_entry" in text:
            target_events.add("zone_entry")

        # Parse time constraints
        min_time = 0.0
        max_time = float("inf")

        # Range: "between 00:10 and 00:20"
        range_match = re.search(r"between (\d+:\d+|\d+) and (\d+:\d+|\d+)", text)
        if range_match:
            min_time = parse_time(range_match.group(1))
            max_time = parse_time(range_match.group(2))
        else:
            # "after 10 seconds" or "after 01:20"
            after_match = re.search(r"after (\d+:\d+|\d+)", text)
            if after_match:
                min_time = parse_time(after_match.group(1))

            # "before 50 seconds" or "before 02:00"
            before_match = re.search(r"before (\d+:\d+|\d+)", text)
            if before_match:
                max_time = parse_time(before_match.group(1))

        # Filter events
        filtered = []
        for event in self.events:
            if event["timestamp_seconds"] < min_time:
                continue
            if event["timestamp_seconds"] > max_time:
                continue
            if target_labels and event["object_label"] not in target_labels:
                continue
            if target_events and event["event_type"] not in target_events:
                continue
            filtered.append(event)

        if not filtered:
            return None

        # Return results
        if is_count:
            return {"count": len(filtered)}

        if sort_descending:
             return filtered[-1]

        return filtered[0]
