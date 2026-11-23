from typing import Dict, Callable, Optional, List
try:
    from groq import Groq
except ImportError:
    Groq = None  # type: ignore
from app.config import settings
from app.utils.cui_calculator import (
    CUICalculator,
    OnboardingGraphBuilder,
    BusinessRiskScorer,
    compute_onboarding_complexity_score,
    PERSONA_WEIGHTS,
)
import json


class AnalystAgent:
    """Analyst Agent v2 - Deep analysis using LLM + CUI v2 + Onboarding Graph + Business Risk"""

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.client = Groq(api_key=settings.GROQ_API_KEY) if Groq else None

    def emit_progress(self, message: str, data: Optional[Dict] = None):
        if self.progress_callback:
            self.progress_callback("analyst", message, data or {})

    # ─────────────────────────────────────────────────────────────────────────
    # CUI v2 computation
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_cui(self, scout_data: Dict, persona_mode: str = "SOLO_DEV") -> Dict:
        """Compute Codebase Understanding Index v2 with persona-weighted variants."""
        self.emit_progress("  Computing CUI v2...")
        weights = PERSONA_WEIGHTS.get(persona_mode, PERSONA_WEIGHTS["SOLO_DEV"])
        calc = CUICalculator(weights=weights)

        structure = scout_data.get("structure", {})
        risk_data = scout_data.get("risk_points", {})
        bus_factor_map = scout_data.get("bus_factor_map", {})

        # Component C: Cyclomatic complexity (inverse, normalised to 0-1)
        # parser returns a flat list under "functions"
        all_fns = structure.get("functions", [])
        avg_complexity = 1.0
        if all_fns:
            complexities = [fn.get("cyclomatic_complexity", 1) for fn in all_fns]
            raw_avg = sum(complexities) / len(complexities)
            avg_complexity = max(0.0, min(1.0, 1 - (raw_avg - 1) / 20))

        # Component F: File count score (too many = hard to navigate)
        total_files = structure.get("file_count", 0)
        file_score = max(0.0, min(1.0, 1 - total_files / 2000))

        # Component H: History score (recent activity = easier to understand context)
        months = scout_data.get("active_period_months", 0)
        last_commit = scout_data.get("last_commit_date", "")
        history_score = 0.5
        if last_commit:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(last_commit[:10])
                months_since = max(0, (datetime.now() - dt).days / 30)
                history_score = max(0.0, min(1.0, 1 - months_since / 60))
            except Exception:
                pass

        # Component I: Import complexity (high fan-in = complex)
        import_graph = structure.get("imports_graph", {})
        fan_in_values = [len(v) for v in import_graph.values()] if import_graph else [0]
        avg_fan_in = sum(fan_in_values) / len(fan_in_values) if fan_in_values else 0
        import_score = max(0.0, min(1.0, 1 - avg_fan_in / 20))

        # Component T: Test coverage signal (presence of test files)
        # parser returns files as list of dicts with "path" key
        all_file_paths = [f["path"] for f in structure.get("files", []) if isinstance(f, dict)]
        test_files = [f for f in all_file_paths if "test" in f.lower() or "spec" in f.lower()]
        test_score = min(1.0, len(test_files) / max(1, total_files) * 10)

        # Component R: Risk score (inverse of risk density)
        risk_findings = risk_data.get("risk_findings", [])
        files_scanned = max(1, risk_data.get("files_scanned", 1))
        risk_density = len(risk_findings) / files_scanned
        risk_score = max(0.0, min(1.0, 1 - risk_density * 5))

        # Component B: Bus factor score (higher = fewer critical single-owner files)
        critical_files = sum(1 for v in bus_factor_map.values() if v.get("critical", False))
        total_tracked = max(1, len(bus_factor_map))
        bus_score = max(0.0, min(1.0, 1 - critical_files / total_tracked))

        # Component D: Documentation coverage — computed from per-file data
        files_with_funcs = [f for f in structure.get("files", []) if isinstance(f, dict) and f.get("function_count", 0) > 0]
        if files_with_funcs:
            doc_score = sum(f.get("doc_coverage", 0.0) for f in files_with_funcs) / len(files_with_funcs)
        else:
            doc_score = 0.0

        components = {
            "complexity": avg_complexity,
            "file_count": file_score,
            "history": history_score,
            "import_complexity": import_score,
            "test_coverage": test_score,
            "risk_score": risk_score,
            "bus_factor": bus_score,
            "documentation": doc_score,
        }
        cui_result = calc.compute(components)
        self.emit_progress(
            f"  ✓ CUI Score: {cui_result['cui_score']:.1f}/100 "
            f"[{cui_result['understanding_label']}] | persona={persona_mode}"
        )
        return cui_result

    # ─────────────────────────────────────────────────────────────────────────
    # Onboarding graph
    # ─────────────────────────────────────────────────────────────────────────

    def _build_onboarding_graph(self, scout_data: Dict) -> Dict:
        self.emit_progress("  Building onboarding DAG...")
        structure = scout_data.get("structure", {})
        import_graph = structure.get("imports_graph", {})
        entry_points = structure.get("entry_points", [])

        if not import_graph:
            # Fallback: build a simple tier list from entry points + file list
            files = structure.get("files", [])
            ep_files = [e["file"] for e in entry_points[:3]]
            all_paths = [f["path"] for f in files if isinstance(f, dict)]

            # Day 1: entry points (or first 3 files)
            day1 = ep_files if ep_files else all_paths[:3]
            # Week 1: next layer of interesting files (config, utils, main modules)
            week1 = [p for p in all_paths[:15] if p not in day1][:6]
            # Week 2: remaining files up to a reasonable cap
            week2 = [p for p in all_paths[15:30] if p not in day1 and p not in week1]

            fallback_graph = {
                "total_nodes": len(all_paths),
                "learning_tiers": {
                    "day_1": day1,
                    "week_1": week1,
                    "week_2": week2,
                },
                "fallback": True,
            }
            self.emit_progress(
                f"  ✓ Fallback tiers built: {len(all_paths)} files | Day-1: {len(day1)}"
            )
            return fallback_graph

        builder = OnboardingGraphBuilder()
        graph = builder.build(import_graph, entry_points)
        day1 = graph.get("learning_tiers", {}).get("day_1", [])
        self.emit_progress(
            f"  ✓ DAG built: {graph.get('total_nodes', 0)} nodes | "
            f"Day-1 tier: {len(day1)} files"
        )
        return graph

    # ─────────────────────────────────────────────────────────────────────────
    # Business risk scoring
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_business_risk(self, scout_data: Dict, onboarding_graph: Dict) -> Dict:
        self.emit_progress("  Computing business risk...")
        scorer = BusinessRiskScorer()
        bus_factor_map = scout_data.get("bus_factor_map", {})
        risk_findings = scout_data.get("risk_points", {}).get("risk_findings", [])
        is_archived = scout_data.get("github_data", {}).get("is_archived", False)

        # Build synthetic CUI scores list from risk findings for score_files()
        synthetic_cui = []
        for finding in risk_findings[:20]:
            fpath = finding.get("file", "unknown")
            synthetic_cui.append({
                "file": fpath,
                "cui_score": 0.7,  # High CUI = risky
                "components": {"C": 0.7, "F": 0.5, "H": 0.5, "I": 0.5,
                               "T": 0.7, "R": 1.0, "B": 0.5, "D": 0.5},
            })

        risk_items = scorer.score_files(synthetic_cui, bus_factor_map)

        # Append archive risk
        if is_archived:
            risk_items.insert(0, {
                "file": "repository",
                "risk_level": "HIGH",
                "risk_name": "Archived Repository",
                "description": "This repository is archived and no longer maintained.",
                "cui_score": 0,
                "bus_factor": 0,
                "top_author": "N/A",
            })

        risk_report = {
            "risk_items": [
                {"level": r["risk_level"], "name": r["risk_name"],
                 "file": r["file"], "description": r["description"]}
                for r in risk_items
            ],
            "total_findings": len(risk_items),
        }
        critical = sum(1 for r in risk_report["risk_items"] if r["level"] == "CRITICAL")
        high = sum(1 for r in risk_report["risk_items"] if r["level"] == "HIGH")
        self.emit_progress(f"  ✓ Business risk: CRITICAL={critical} HIGH={high}")
        return risk_report

    # ─────────────────────────────────────────────────────────────────────────
    # LLM hypothesis (unchanged in shape, enriched with new context)
    # ─────────────────────────────────────────────────────────────────────────

    def build_analysis_prompt(self, scout_data: Dict, cui_result: Dict, ocs: int) -> str:
        patterns_summary = []
        if scout_data.get("patterns_detected"):
            patterns = scout_data["patterns_detected"]
            if "activity_spike" in patterns:
                s = patterns["activity_spike"]
                patterns_summary.append(f"- Activity spike in {s['month']} with {s['commit_count']} commits")
            if "sudden_stop" in patterns:
                s = patterns["sudden_stop"]
                patterns_summary.append(
                    f"- Sudden halt: last activity {s['last_activity']} ({s['months_since']:.0f} months ago)"
                )
            if "gradual_decay" in patterns:
                s = patterns["gradual_decay"]
                patterns_summary.append(f"- Gradual decay: {s['decline_percentage']:.0f}% decline")

        web_summary = []
        for _, results in scout_data.get("web_search_results", {}).items():
            for r in results:
                web_summary.append(f"- [{r['title']}] {r['snippet']}\n  {r.get('full_content','')[:400]}")

        risk_summary = []
        sev = scout_data.get("risk_points", {}).get("severity_summary", {})
        if sev:
            risk_summary.append(
                f"Static scan: CRITICAL={sev.get('CRITICAL',0)} HIGH={sev.get('HIGH',0)} "
                f"MEDIUM={sev.get('MEDIUM',0)} LOW={sev.get('LOW',0)}"
            )

        community = scout_data.get("community", {})
        community_summary = []
        if community:
            community_summary.append(f"Open issues: {community.get('open_issues', 0)}")
            community_summary.append(f"Open PRs: {community.get('open_prs', 0)}")
            health = community.get("community_health", {})
            if health:
                community_summary.append(f"Health score: {health.get('health_percentage', 0)}%")

        prompt = f"""You are an expert code archaeologist and software analyst.

## Repository: {scout_data['repo_name']}
## Basic Stats:
- Total Commits: {scout_data['total_commits']}
- Contributors: {scout_data['contributors_count']}
- First Commit: {scout_data['first_commit_date']}
- Last Commit: {scout_data['last_commit_date']}
- Active Period: {scout_data['active_period_months']:.1f} months

## Code Quality Metrics:
- CUI Score: {cui_result.get('cui_score', 0):.1f}/100 ({cui_result.get('understanding_label', 'N/A')})
- Onboarding Complexity Score: {ocs}/100
- Bus Factor: {scout_data.get('bus_factor_map') and len([v for v in scout_data.get('bus_factor_map',{}).values() if v.get('is_critical')]) or 0} critical single-owner files

## Risk Signals:
{chr(10).join(risk_summary) if risk_summary else "No static risk data"}

## Community Health:
{chr(10).join(community_summary) if community_summary else "No community data"}

## Git Patterns Detected:
{chr(10).join(patterns_summary) if patterns_summary else "No significant patterns"}

## External Web Findings:
{chr(10).join(web_summary[:5]) if web_summary else "No web context found"}

## Top Contributors:
{chr(10).join([f"- {c.get('name', c.get('username','Unknown'))}: {c.get('commit_count', c.get('contributions',0))} commits" for c in scout_data.get('top_contributors',[])[:3]])}

---

Your task: Analyze all available data and provide a comprehensive hypothesis about this repository.

Respond in JSON format:
{{
    "hypothesis": "Clear, concise statement about what happened",
    "confidence": 0-100,
    "reasoning": ["reason 1", "reason 2", "reason 3"],
    "evidence_quality": "strong/medium/weak",
    "needs_more_evidence": true/false,
    "key_findings": ["finding 1", "finding 2"],
    "likely_cause": "abandonment/archived/migration/active/maintenance-mode/unknown",
    "technical_health": "excellent/good/fair/poor",
    "onboarding_difficulty": "easy/moderate/complex/very-complex",
    "salvageability": "high/medium/low/none"
}}

Consider CUI score, OCS, bus factor, risk signals AND git patterns. Be objective."""
        return prompt

    def parse_llm_response(self, response_text: str) -> Dict:
        try:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start != -1 and end != 0:
                result = json.loads(response_text[start:end])
                for field in ["hypothesis", "confidence", "reasoning"]:
                    if field not in result:
                        raise ValueError(f"Missing: {field}")
                result["confidence"] = max(0, min(100, int(result["confidence"])))
                return result
            raise ValueError("No JSON in response")
        except Exception as e:
            self.emit_progress(f"LLM parse failed: {e}")
            return {
                "hypothesis": "Unable to form hypothesis from available data",
                "confidence": 30,
                "reasoning": ["Insufficient data"],
                "evidence_quality": "weak",
                "needs_more_evidence": True,
                "key_findings": [],
                "likely_cause": "unknown",
                "technical_health": "unknown",
                "onboarding_difficulty": "unknown",
                "salvageability": "unknown",
            }

    def analyze(
        self,
        scout_data: Dict,
        previous_analysis: Optional[Dict] = None,
        persona_mode: str = "SOLO_DEV",
    ) -> Dict:
        """Run full analysis: CUI + Onboarding Graph + Business Risk + LLM Hypothesis."""
        self.emit_progress("Analyst Agent v2 activated", {"persona": persona_mode})

        # Step 1 — CUI v2
        self.emit_progress("Step 1/4 — CUI v2 computation")
        cui_result = self._compute_cui(scout_data, persona_mode)

        # Step 2 — Onboarding graph
        self.emit_progress("Step 2/4 — Onboarding graph")
        onboarding_graph = self._build_onboarding_graph(scout_data)

        # Step 3 — OCS
        self.emit_progress("Step 3/4 — Onboarding Complexity Score")
        total_files = scout_data.get("structure", {}).get("file_count", 0)
        agg_components = cui_result.get("components", {})
        # Build a synthetic per-file list from aggregate scores for OCS computation
        # cui_score must be in 0-1 range (OCS function scales by *100 internally)
        synthetic_cui_scores = [{
            "cui_score": cui_result.get("normalised_score", 0.5),
            "components": {
                "C": 1.0 - agg_components.get("complexity", 0.5),
                "F": 1.0 - agg_components.get("import_complexity", 0.5),
                "H": 1.0 - agg_components.get("history", 0.5),
                "I": 0.3,
                "T": 1.0 - agg_components.get("test_coverage", 0.5),
                "R": 1.0 - agg_components.get("risk_score", 0.5),
                "B": 1.0 - agg_components.get("bus_factor", 0.5),
                "D": 1.0 - agg_components.get("documentation", 0.5),
            }
        }]
        ocs_result = compute_onboarding_complexity_score(
            cui_scores=synthetic_cui_scores,
            file_count=total_files,
        )
        ocs = ocs_result.get("ocs_score", 0)
        self.emit_progress(f"  OCS: {ocs}/100 ({_ocs_label(ocs)})")

        # Step 4 — Business risk
        self.emit_progress("Step 4/4 — Business risk scoring")
        business_risk = self._compute_business_risk(scout_data, onboarding_graph)

        # LLM hypothesis
        self.emit_progress("Consulting AI for pattern interpretation...")
        try:
            prompt = self.build_analysis_prompt(scout_data, cui_result, ocs)
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert software archaeologist specialising in analysing "
                            "codebases. You provide data-driven insights from git history, code "
                            "quality metrics, risk signals, and community data."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                model="llama-3.1-70b-versatile",
                temperature=0.3,
                max_tokens=1200,
            )
            analysis = self.parse_llm_response(response.choices[0].message.content)
        except Exception as e:
            self.emit_progress(f"LLM call failed: {e}")
            analysis = self.parse_llm_response("")

        confidence = analysis["confidence"]
        self.emit_progress(f"Hypothesis: {analysis['hypothesis'][:100]}...", {"confidence": confidence})
        self.emit_progress(f"Confidence: {confidence}%")

        if confidence < 70:
            self.emit_progress("⚠ Confidence below 70% — more evidence recommended", {"needs_verification": True})
            analysis["needs_more_evidence"] = True
        else:
            self.emit_progress("✓ Confidence sufficient for report", {"needs_verification": False})
            analysis["needs_more_evidence"] = False

        # Attach computed scores to analysis result
        analysis["cui_scores"] = cui_result
        analysis["onboarding_graph"] = onboarding_graph
        analysis["ocs_score"] = ocs
        analysis["ocs_label"] = _ocs_label(ocs)
        analysis["business_risk"] = business_risk

        return analysis


def _ocs_label(ocs: int) -> str:
    if ocs <= 25:
        return "Easy"
    elif ocs <= 50:
        return "Moderate"
    elif ocs <= 75:
        return "Complex"
    return "Very Complex"
    
