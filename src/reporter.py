from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class IncidentReporter:
    """Generates structured Markdown security audit reports."""

    @staticmethod
    def calculate_risk_assessment(events: list[dict], duration_seconds: float = 0.0) -> dict:
        """Calculates risk score (0-100) and risk level (LOW/MEDIUM/HIGH/CRITICAL)."""
        score = 0
        factors = []

        unattended_count = sum(1 for e in events if e["event_type"] == "unattended")
        breach_count = sum(1 for e in events if e["event_type"] == "zone_breach")
        loitering_count = sum(1 for e in events if e["event_type"] == "loitering")

        if unattended_count > 0:
            score += unattended_count * 30
            factors.append(f"{unattended_count} unattended objects detected (+{unattended_count * 30} risk)")
        if breach_count > 0:
            score += breach_count * 25
            factors.append(f"{breach_count} restricted zone breaches (+{breach_count * 25} risk)")
        if loitering_count > 0:
            score += loitering_count * 15
            factors.append(f"{loitering_count} loitering incidents (+{loitering_count * 15} risk)")

        score = min(score, 100)

        if score >= 80:
            level = "CRITICAL"
        elif score >= 50:
            level = "HIGH"
        elif score >= 20:
            level = "MEDIUM"
        else:
            level = "LOW"

        if not factors:
            factors.append("Routine traffic observed. No elevated risk factors.")

        return {"score": score, "level": level, "factors": factors}

    @staticmethod
    def generate_recommendations(risk_level: str, events: list[dict]) -> list[str]:
        recommendations = []
        if any(e["event_type"] == "unattended" for e in events):
            recommendations.append("⚠ Unattended objects detected: Ensure staff are trained to address abandoned luggage promptly.")
        if any(e["event_type"] == "zone_breach" for e in events):
            recommendations.append("🛑 Zone Breaches: Consider stricter physical barriers or visible signage around restricted ROI zones.")
        if any(e["event_type"] == "loitering" for e in events):
            recommendations.append("👀 Loitering: Monitor areas where subjects tend to dwell. Personnel dispatch may be necessary for prolonged loitering.")

        if risk_level == "LOW":
            recommendations.append("✓ Security posture appears stable. Continue standard operating monitoring.")

        return recommendations

    def generate_offline_report(self, video_meta: dict, events: list[dict]) -> str:
        risk = self.calculate_risk_assessment(events, video_meta.get("duration_seconds", 0))
        recs = self.generate_recommendations(risk["level"], events)

        md = [
            "# 🛡️ CCTV Security Incident Audit Report",
            f"**Video Analyzed:** `{video_meta['filename']}`",
            f"**Report Generated:** `{video_meta.get('created_at', 'Now')}`",
            "",
            "## 1. Executive Summary",
            f"Overall Risk Assessment Level is **{risk['level']}** (Score: {risk['score']}/100).",
            "",
            "### Threat Factors:"
        ]
        for f in risk["factors"]:
            md.append(f"- {f}")
        md.append("")

        md.append("## 2. Key Metrics")
        md.append(f"- Duration Analyzed: {video_meta.get('duration_seconds', 0):.1f}s")
        md.append(f"- Total Tracked Events: {len(events)}")
        md.append("")

        md.append("## 3. High-Severity Incident Timeline")
        critical_events = [e for e in events if e["event_type"] in ["unattended", "zone_breach", "loitering"]]
        if not critical_events:
            md.append("*No high-severity incidents detected in this analysis window.*")
        else:
            for e in sorted(critical_events, key=lambda x: x["timestamp_seconds"]):
                time_str = f"{int(e['timestamp_seconds']) // 60:02d}:{int(e['timestamp_seconds']) % 60:02d}"
                md.append(f"- **[{time_str}]** {e['event_type'].upper()}: {e['object_label'].title()} #{e['tracking_id']} ({e.get('details', '')})")
        md.append("")

        md.append("## 4. Operational Recommendations")
        for r in recs:
            md.append(f"- {r}")

        return "\n".join(md)

    def generate_claude_report(self, video_meta: dict, events: list[dict], api_key: str) -> str:
        try:
            import anthropic
        except ImportError:
            return self.generate_offline_report(video_meta, events)

        client = anthropic.Anthropic(api_key=api_key)
        risk = self.calculate_risk_assessment(events, video_meta.get("duration_seconds", 0))
        critical_events = [e for e in events if e["event_type"] in ["unattended", "zone_breach", "loitering"]]

        system_prompt = (
            "You are an expert physical security auditor analyzing CCTV footage results. "
            "Generate a professional, structured Markdown incident report."
        )

        user_content = f"""
        Conduct a Security Audit based on this CCTV pipeline output:
        Video: {video_meta['filename']}
        Duration: {video_meta.get('duration_seconds', 0):.1f}s
        Calculated Risk: {risk['level']} ({risk['score']} / 100)
        Total Events: {len(events)}

        Critical Incidents:
        {critical_events}

        Provide:
        1. Executive Summary
        2. Threat Assessment
        3. Incident Narrative (Chronological)
        4. Strategic Security Recommendations
        """

        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
            first_block = response.content[0]
            if hasattr(first_block, "text"):
                return str(first_block.text)
            return str(first_block)
        except Exception as e:
            logger.exception("AI report generation failed")
            return (
                "*(AI report generation failed. Falling back to offline report.)*\n\n"
                + self.generate_offline_report(video_meta, events)
            )

    def generate_report(self, video_meta: dict, events: list[dict], api_key: str | None = None) -> str:
        if api_key:
            return self.generate_claude_report(video_meta, events, api_key)
        return self.generate_offline_report(video_meta, events)
