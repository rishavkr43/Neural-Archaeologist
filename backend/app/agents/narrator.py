from typing import Dict, Callable, List, Optional
from groq import Groq
from app.config import settings
from datetime import datetime


# ─── Persona Report Templates ─────────────────────────────────────────────────

PERSONA_REPORT_STRUCTURE = {
    "SOLO_DEV": {
        "title": "Solo Developer Report",
        "sections": [
            "quick_summary",
            "day1_learning_path",
            "key_files_to_read",
            "bus_factor_warnings",
            "safe_first_pr",
            "tech_debt_hotspots",
            "recommendations",
        ],
        "tone": "practical and concise — you are giving advice to a developer who will work alone",
    },
    "STARTUP": {
        "title": "Startup Due-Diligence Report",
        "sections": [
            "executive_summary",
            "business_risk_assessment",
            "technical_debt_cost",
            "onboarding_timeline",
            "team_acquisition_risk",
            "build_vs_buy_verdict",
            "recommendations",
        ],
        "tone": "business-focused, risk-aware — leadership needs decision ammunition",
    },
    "ENTERPRISE": {
        "title": "Enterprise Architecture Report",
        "sections": [
            "executive_summary",
            "security_compliance_scan",
            "architectural_complexity",
            "scalability_assessment",
            "migration_effort_estimate",
            "vendor_dependency_risk",
            "recommendations",
        ],
        "tone": "formal and structured — enterprise architects need thorough risk analysis",
    },
    "OSS_MAINTAINER": {
        "title": "Open Source Maintainer Report",
        "sections": [
            "project_health",
            "contributor_diversity",
            "issue_pr_velocity",
            "onboarding_experience",
            "documentation_gaps",
            "safe_first_pr_candidates",
            "community_recommendations",
        ],
        "tone": "community-oriented, welcoming — focus on sustainability and contributor growth",
    },
}


class NarratorAgent:
    """Narrator Agent v2 — Persona-aware report generation for 4 audience modes."""

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.client = Groq(api_key=settings.GROQ_API_KEY)

    def emit_progress(self, message: str, data: Optional[Dict] = None):
        if self.progress_callback:
            self.progress_callback("narrator", message, data or {})

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────────
    # Glossary
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _glossary() -> str:
        return """
---

## 📖 Terms Explained

| Term | What it means |
|------|---------------|
| **CUI Score** | 0–100. How easy this codebase is to understand. Higher = easier. |
| **OCS** *(Onboarding Complexity)* | 0–100. How hard it is for a new dev to get productive. Higher = harder. |
| **Bus Factor** | How many people carry critical knowledge. Bus factor 1 = one person leaving breaks everything. |
| **Cyclomatic Complexity** | How many decision paths are in the code. High = harder to read and test. |
| **Tech Debt** | Shortcuts taken during development that will cost extra effort to fix later. |
| **Fan-in / Fan-out** | Fan-in = files that depend on this file. Fan-out = files this file depends on. |
| **DAG** *(Learning Path)* | A recommended reading order for files, from foundational to advanced. |
| **CRITICAL / HIGH / MEDIUM / LOW** | Risk severity. CRITICAL = fix now (e.g. hardcoded secrets). LOW = monitor. |
| **Salvageability** | Whether this codebase is worth reusing, partially adapting, or discarding. |
| **Persona Mode** | Who this report is written for: developer, startup team, enterprise architect, or OSS maintainer. |
| **Good First Issue** | A GitHub-tagged task suitable for newcomers — small scope, low risk. |
| **Stale PR** | A pull request untouched for 90+ days — signals a review backlog or abandoned work. |
"""

    def has_web_evidence(self, scout_data: Dict) -> bool:
        for _, results in scout_data.get("web_search_results", {}).items():
            for r in results:
                if r.get("full_content") or r.get("snippet"):
                    return True
        return False

    def _format_web_evidence(self, scout_data: Dict) -> str:
        parts = []
        c = 1
        for _, results in scout_data.get("web_search_results", {}).items():
            for r in results:
                parts.append(
                    f"[Source {c}] {r['title']}\nURL: {r['link']}\n"
                    f"Snippet: {r.get('snippet','')}\n"
                    f"Content: {r.get('full_content','')[:800]}"
                )
                c += 1
        return "\n\n".join(parts) if parts else "No external web sources."

    def _format_learning_path(self, analysis: Dict) -> str:
        og = analysis.get("onboarding_graph", {})
        tiers = og.get("learning_tiers", {})
        if not tiers:
            return "No learning path available."
        lines = []
        for tier, files in tiers.items():
            lines.append(f"**{tier.upper()}**: {', '.join(files[:5])}" + (" ..." if len(files) > 5 else ""))
        return "\n".join(lines)

    def _format_bus_factor(self, scout_data: Dict) -> str:
        bf_map = scout_data.get("bus_factor_map", {})
        if not bf_map:
            return "Bus factor data unavailable."
        critical = [(k, v) for k, v in bf_map.items() if v.get("critical", False)]
        if not critical:
            return "No critical single-owner files detected."
        lines = [f"- `{f}` — top author owns {v.get('top_author_pct',0)*100:.0f}% of commits" for f, v in critical[:10]]
        return "\n".join(lines)

    def _format_safe_first_pr(self, scout_data: Dict) -> str:
        gfi = scout_data.get("community", {}).get("good_first_issues", [])
        if not gfi:
            return "No tagged good-first-issues found. Consider exploring test files or documentation gaps."
        lines = [f"- #{i['number']}: {i['title']} — {i['url']}" for i in gfi[:5]]
        return "\n".join(lines)

    def _format_risk_findings(self, scout_data: Dict) -> str:
        findings = scout_data.get("risk_points", {}).get("risk_findings", [])
        critical_high = [f for f in findings if f["severity"] in ("CRITICAL", "HIGH")]
        if not critical_high:
            return "No critical/high risk patterns detected."
        lines = [
            f"- [{f['severity']}] `{f['file']}` — {f['pattern']} ({f['occurrences']}x)"
            for f in critical_high[:10]
        ]
        return "\n".join(lines)

    def _format_business_risk(self, analysis: Dict) -> str:
        br = analysis.get("business_risk", {})
        items = br.get("risk_items", [])
        if not items:
            return "No significant business risks identified."
        lines = [f"- **[{r['level']}]** {r['title']}: {r['description']}" for r in items[:6]]
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Prompt builders
    # ─────────────────────────────────────────────────────────────────────────

    def _format_patterns(self, scout_data: Dict) -> str:
        patterns = scout_data.get("patterns_detected", {})
        lines = []
        if "activity_spike" in patterns:
            s = patterns["activity_spike"]
            lines.append(f"- Activity spike in {s['month']}: {s['commit_count']} commits (avg {s['average']})")
        if "sudden_stop" in patterns:
            s = patterns["sudden_stop"]
            lines.append(f"- Sudden stop: last commit {s['last_activity']} ({s['months_since']:.0f} months ago)")
        if "gradual_decay" in patterns:
            s = patterns["gradual_decay"]
            lines.append(f"- Gradual decay: {s['decline_percentage']:.0f}% decline (early avg {s['early_avg']} → later avg {s['later_avg']})")
        return "\n".join(lines) if lines else "- No significant activity patterns detected"

    def _build_story_block(self, scout_data: Dict, analysis: Dict) -> str:
        """Three-act narrative block — always included, citation behaviour is conditional."""
        has_web = self.has_web_evidence(scout_data)
        citation_instruction = (
            "CRITICAL: You HAVE web sources below. In Act III, cite them specifically — "
            "e.g. 'According to [Source Name]...' or 'The GitHub archive page indicates...'. "
            "Use actual facts from the full content, not vague references like 'sources suggest'."
            if has_web else
            "No external web sources were found. Base the narrative ONLY on git patterns."
        )

        return f"""
## ── PART 1: THE STORY ──────────────────────────────────────────────────────

Be concise — each act is ONE tight paragraph (3-5 sentences max). No padding.
{citation_instruction}

### ACT I: THE BIRTH
1 paragraph: when it started, who, what problem it solved. Ground every claim in the timeline data.

### ACT II: THE GOLDEN AGE
1 paragraph: the peak activity month, key contributors, what was being built most actively.

### ACT III: THE DECLINE
1 paragraph: what pattern caused the slowdown.
{"Cite specific facts from the web sources (author/company names, direct quotes)." if has_web else "Based solely on git patterns."}

### 🔍 KEY FINDINGS
3-5 bullet points only — the most critical discoveries, each one sentence.

### 💡 SALVAGEABILITY
One line verdict (HIGHLY SALVAGEABLE / PARTIALLY SALVAGEABLE / NOT SALVAGEABLE) + one sentence justification.

{"### 📚 SOURCES" + chr(10) + self._format_web_evidence(scout_data) if has_web else ""}
"""

    def _build_prompt(self, scout_data: Dict, analysis: Dict, persona_mode: str) -> str:
        struct = PERSONA_REPORT_STRUCTURE.get(persona_mode, PERSONA_REPORT_STRUCTURE["SOLO_DEV"])
        sections_str = "\n".join(f"- {s}" for s in struct["sections"])

        data_block = f"""
Repository: {scout_data.get('repo_name', 'Unknown')}
Hypothesis: {analysis.get('hypothesis', '')}
Confidence: {analysis.get('confidence', 0)}%
Technical Health: {analysis.get('technical_health', 'N/A')}
Likely Cause: {analysis.get('likely_cause', 'unknown')}
Salvageability: {analysis.get('salvageability', 'unknown')}

Timeline: {scout_data.get('first_commit_date', '?')} → {scout_data.get('last_commit_date', '?')}
Commits: {scout_data.get('total_commits', 0)} | Contributors: {scout_data.get('contributors_count', 0)} | Active months: {scout_data.get('active_period_months', 0):.1f}

Git Patterns:
{self._format_patterns(scout_data)}

CUI Score: {analysis.get('cui_scores', {}).get('cui_score', 0):.1f}/100 ({analysis.get('cui_scores', {}).get('understanding_label', 'N/A')})
Onboarding Complexity: {analysis.get('ocs_score', 0)}/100 ({analysis.get('ocs_label', 'N/A')})

Learning Path:
{self._format_learning_path(analysis)}

Bus Factor Risks:
{self._format_bus_factor(scout_data)}

Security / Risk Findings:
{self._format_risk_findings(scout_data)}

Business Risks:
{self._format_business_risk(analysis)}

Safe First PR:
{self._format_safe_first_pr(scout_data)}

Key Findings:
{chr(10).join(f'- {f}' for f in analysis.get('key_findings', []))}

Web Evidence:
{self._format_web_evidence(scout_data)}
"""

        story_block = self._build_story_block(scout_data, analysis)

        return f"""You are generating a Neural Archaeologist Report.
The report has TWO parts. Write BOTH. Be dense and data-driven — no filler prose.

# 🔬 Neural Archaeologist Report: {scout_data.get('repo_name', 'Unknown')}
**Persona Mode:** {persona_mode} | **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---
## INTELLIGENCE DATA (use this for everything below):
{data_block}
---

{story_block}

## ── PART 2: {struct['title'].upper()} ──────────────────────────────────────

Tone: {struct['tone']}

Write the persona-specific analysis. Include EXACTLY these sections (use ## headers):
{sections_str}

Instructions:
- Each section: 1-2 focused paragraphs or a tight bullet list. No watering down.
- Use CUI score, OCS, bus factor numbers directly.
- For SOLO_DEV: where to start reading and what to avoid.
- For STARTUP: clear risk/cost/timeline recommendation.
- For ENTERPRISE: compliance signals and migration complexity.
- For OSS_MAINTAINER: contributor experience and community health.
- End Part 2 with a **Verdict** — one punchy paragraph on what this repo is worth."""

    # ─────────────────────────────────────────────────────────────────────────
    # Timeline & contributor helpers (unchanged shape)
    # ─────────────────────────────────────────────────────────────────────────

    def generate_timeline(self, scout_data: Dict, analysis: Dict) -> list:
        timeline = []
        if scout_data.get("first_commit_date"):
            timeline.append({
                "date": scout_data["first_commit_date"],
                "event": "Project Inception",
                "description": f"First commit to {scout_data['repo_name']}",
                "type": "birth",
            })
        patterns = scout_data.get("patterns_detected", {})
        if "activity_spike" in patterns:
            spike = patterns["activity_spike"]
            timeline.append({
                "date": spike["month"],
                "event": "Peak Development",
                "description": f"Activity spike: {spike['commit_count']} commits",
                "type": "peak",
            })
        if "sudden_stop" in patterns:
            stop = patterns["sudden_stop"]
            timeline.append({
                "date": stop["last_activity"],
                "event": "Development Ceased",
                "description": f"Last commit — {stop['months_since']:.0f} months ago",
                "type": "decline",
            })
        timeline.append({
            "date": datetime.now().isoformat(),
            "event": "Archaeological Investigation",
            "description": "Neural Archaeologist v2 analysis completed",
            "type": "present",
        })
        return sorted(timeline, key=lambda x: x["date"])

    def format_contributor_profiles(self, scout_data: Dict) -> str:
        profiles = []
        total = scout_data.get("total_commits", 1)
        for c in scout_data.get("top_contributors", [])[:5]:
            name = c.get("name", c.get("username", "Unknown"))
            commits = c.get("commit_count", c.get("contributions", 0))
            pct = c.get("percentage", round(commits / total * 100, 1) if total > 0 else 0)
            role = "Lead Developer" if pct > 30 else ("Core Contributor" if pct > 10 else "Regular Contributor")
            profiles.append(f"### {name}\n- **Commits:** {commits} ({pct}%)\n- **Impact:** {role}")
        return "\n\n".join(profiles) if profiles else "No contributor data."

    def extract_citations(self, scout_data: Dict) -> list:
        citations = []
        n = 1
        for _, results in scout_data.get("web_search_results", {}).items():
            for r in results:
                citations.append({
                    "number": n,
                    "title": r.get("title", "Unknown"),
                    "url": r.get("link", ""),
                    "source": r.get("source", "Unknown"),
                    "snippet": r.get("snippet", ""),
                })
                n += 1
        return citations

    # ─────────────────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────────────────

    def generate_report(
        self,
        scout_data: Dict,
        analysis: Dict,
        persona_mode: str = "SOLO_DEV",
    ) -> Dict:
        self.emit_progress("Narrator Agent v2 activated", {"persona": persona_mode})
        self.emit_progress(f"Generating {PERSONA_REPORT_STRUCTURE[persona_mode]['title']}...")

        has_web = self.has_web_evidence(scout_data)
        if has_web:
            self.emit_progress("  ↳ Incorporating web evidence with citations")

        try:
            prompt = self._build_prompt(scout_data, analysis, persona_mode)
            completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert technical writer and investigative analyst. "
                            "Produce structured Markdown reports tailored to your audience. "
                            "When web sources are available, cite them specifically. "
                            "Always ground claims in the provided data."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                model=settings.GROQ_MODEL,
                temperature=0.7,
                max_tokens=2000,
            )
            narrative = completion.choices[0].message.content + self._glossary()
            self.emit_progress("  ✓ Narrative generated")

            timeline = self.generate_timeline(scout_data, analysis)
            contributor_profiles = self.format_contributor_profiles(scout_data)
            citations = self.extract_citations(scout_data) if has_web else []

            # Build Safe First PR section
            safe_pr = {
                "good_first_issues": scout_data.get("community", {}).get("good_first_issues", []),
                "suggestion": (
                    "Look for test files and documentation gaps as entry points "
                    "if no labelled issues are available."
                ),
            }

            report = {
                "narrative": narrative,
                "timeline": timeline,
                "contributor_profiles": contributor_profiles,
                "citations": citations,
                "has_external_sources": has_web,
                "persona_mode": persona_mode,
                "safe_first_pr": safe_pr,
                "learning_path": analysis.get("onboarding_graph", {}).get("learning_tiers", {}),
                "bus_factor_summary": self._format_bus_factor(scout_data),
                "executive_summary": {
                    "repo_name": scout_data.get("repo_name", ""),
                    "repo_url": scout_data.get("repo_url", ""),
                    "total_commits": scout_data.get("total_commits", 0),
                    "contributors": scout_data.get("contributors_count", 0),
                    "first_commit": scout_data.get("first_commit_date"),
                    "last_commit": scout_data.get("last_commit_date"),
                    "active_months": scout_data.get("active_period_months", 0),
                    "hypothesis": analysis.get("hypothesis", ""),
                    "confidence": analysis.get("confidence", 0),
                    "status": analysis.get("likely_cause", "unknown"),
                    "cui_score": analysis.get("cui_scores", {}).get("cui_score", 0),
                    "ocs_score": analysis.get("ocs_score", 0),
                    "technical_health": analysis.get("technical_health", "N/A"),
                    "salvageability": analysis.get("salvageability", "unknown"),
                },
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "confidence": analysis.get("confidence", 0),
                    "evidence_quality": analysis.get("evidence_quality", "unknown"),
                    "sources_found": len(citations),
                    "persona_mode": persona_mode,
                },
            }
            self.emit_progress("Report generation complete!")
            return report

        except Exception as e:
            self.emit_progress(f"Report generation failed: {e}")
            return {
                "narrative": f"# Error\n\nFailed to generate narrative: {e}",
                "timeline": [],
                "contributor_profiles": "Error generating profiles",
                "citations": [],
                "has_external_sources": False,
                "persona_mode": persona_mode,
                "safe_first_pr": {},
                "learning_path": {},
                "bus_factor_summary": "",
                "executive_summary": {},
                "metadata": {"error": str(e)},
                "error": str(e),
            }
