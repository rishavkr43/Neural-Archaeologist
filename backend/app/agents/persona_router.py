"""
Persona Router Agent — The first agent to run in the v2 pipeline.
Classifies the interaction into one of four operating modes:
SOLO_DEV, STARTUP, ENTERPRISE, OSS_MAINTAINER.

Every downstream agent reads persona_mode from state and adjusts behavior accordingly.
"""

from typing import Dict, Callable, Literal, Optional
try:
    from groq import Groq  # type: ignore[import-untyped]
except ImportError:
    Groq = None  # type: ignore[assignment]
from app.config import settings
from app.utils.cui_calculator import PERSONA_WEIGHTS
from app.utils.prompt_serialization import linearize_json, json_to_toon, is_flat_toon
import json


PersonaMode = Literal["SOLO_DEV", "STARTUP", "ENTERPRISE", "OSS_MAINTAINER"]


class PersonaRouterAgent:
    """
    Persona Router — classifies the user/repo context into one of four modes.
    
    Modes:
    - SOLO_DEV: Individual user, small/medium repo, exploratory language
    - STARTUP: Team signals, fast-growing repo, issue density high, test gaps
    - ENTERPRISE: Org tokens, large repo (>5000 files), compliance keywords, multi-team
    - OSS_MAINTAINER: Public repo, contributor diversity, CONTRIBUTING.md signals
    """

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.client = Groq(api_key=settings.GROQ_API_KEY) if Groq else None

    def emit_progress(self, message: str, data: Optional[Dict] = None):
        if self.progress_callback:
            self.progress_callback("persona_router", message, data or {})

    def classify(self, repo_metadata: Dict, user_context: Optional[Dict] = None) -> Dict:
        """
        Classify the persona mode based on repo metadata and optional user context.
        
        Args:
            repo_metadata: Basic repo info (file_count, stars, forks, languages, 
                          has_contributing, is_public, open_issues, contributors_count, etc.)
            user_context: Optional dict with user_type, organization, question, declared_persona
            
        Returns:
            Dict with persona_mode, confidence, reasoning
        """
        self.emit_progress("Persona Router activated — classifying interaction mode")

        # Try heuristic classification first (fast, no LLM call needed)
        heuristic_result = self._heuristic_classify(repo_metadata, user_context)
        
        if heuristic_result["confidence"] >= 0.80:
            self.emit_progress(
                f"Persona classified (heuristic): {heuristic_result['persona_mode']}",
                {"confidence": heuristic_result["confidence"]}
            )
            return heuristic_result

        # Fall back to LLM classification for ambiguous cases
        self.emit_progress("Ambiguous signals — using LLM for persona classification")
        return self._llm_classify(repo_metadata, user_context)

    def _heuristic_classify(self, repo_metadata: Dict, user_context: Optional[Dict] = None) -> Dict:
        """Fast rule-based classification."""
        
        # Check for user-declared persona first
        if user_context and user_context.get("declared_persona"):
            declared = user_context["declared_persona"].upper()
            if declared in PERSONA_WEIGHTS:
                return {
                    "persona_mode": declared,
                    "confidence": 0.95,
                    "reasoning": ["User explicitly declared persona mode"],
                    "weights": PERSONA_WEIGHTS[declared]
                }
        
        file_count = repo_metadata.get("file_count", 0)
        contributors = repo_metadata.get("contributors_count", 1)
        stars = repo_metadata.get("stars", 0)
        forks = repo_metadata.get("forks", 0)
        open_issues = repo_metadata.get("open_issues", 0)
        has_contributing = repo_metadata.get("has_contributing", False)
        is_public = repo_metadata.get("is_public", True)
        is_archived = repo_metadata.get("is_archived", False)
        has_codeowners = repo_metadata.get("has_codeowners", False)
        
        scores = {"SOLO_DEV": 0, "STARTUP": 0, "ENTERPRISE": 0, "OSS_MAINTAINER": 0}
        reasons = {"SOLO_DEV": [], "STARTUP": [], "ENTERPRISE": [], "OSS_MAINTAINER": []}
        
        # --- File count signals ---
        if file_count < 200:
            scores["SOLO_DEV"] += 2
            reasons["SOLO_DEV"].append(f"Small repo ({file_count} files)")
        elif file_count < 2000:
            scores["STARTUP"] += 1
            scores["OSS_MAINTAINER"] += 1
            reasons["STARTUP"].append(f"Medium repo ({file_count} files)")
        else:
            scores["ENTERPRISE"] += 3
            reasons["ENTERPRISE"].append(f"Large repo ({file_count} files)")
        
        # --- Contributor signals ---
        if contributors <= 2:
            scores["SOLO_DEV"] += 2
            reasons["SOLO_DEV"].append(f"Few contributors ({contributors})")
        elif contributors <= 15:
            scores["STARTUP"] += 2
            reasons["STARTUP"].append(f"Small team ({contributors} contributors)")
        else:
            scores["OSS_MAINTAINER"] += 2
            scores["ENTERPRISE"] += 1
            reasons["OSS_MAINTAINER"].append(f"Many contributors ({contributors})")
        
        # --- Community signals ---
        if stars > 100 and is_public:
            scores["OSS_MAINTAINER"] += 2
            reasons["OSS_MAINTAINER"].append(f"Popular OSS project ({stars} stars)")
        
        if forks > 50:
            scores["OSS_MAINTAINER"] += 1
            reasons["OSS_MAINTAINER"].append(f"Active forking ({forks} forks)")
        
        if has_contributing:
            scores["OSS_MAINTAINER"] += 2
            reasons["OSS_MAINTAINER"].append("Has CONTRIBUTING.md")
        
        # --- Issue density ---
        if open_issues > 50:
            scores["STARTUP"] += 1
            scores["OSS_MAINTAINER"] += 1
            reasons["STARTUP"].append(f"High issue density ({open_issues} open)")
        
        # --- Enterprise signals ---
        if has_codeowners:
            scores["ENTERPRISE"] += 2
            reasons["ENTERPRISE"].append("Has CODEOWNERS file")
        
        if not is_public:
            scores["ENTERPRISE"] += 2
            scores["STARTUP"] += 1
            reasons["ENTERPRISE"].append("Private repository")
        
        # Pick the winner
        winner = max(scores, key=lambda k: scores[k])
        max_score = scores[winner]
        total_score = sum(scores.values()) or 1
        confidence = round(max_score / total_score, 2)
        
        return {
            "persona_mode": winner,
            "confidence": confidence,
            "reasoning": reasons[winner],
            "all_scores": scores,
            "weights": PERSONA_WEIGHTS[winner]
        }

    def _llm_classify(self, repo_metadata: Dict, user_context: Optional[Dict] = None) -> Dict:
        """LLM-based classification for ambiguous cases."""
        repo_linear = linearize_json(repo_metadata)
        user_linear = linearize_json(user_context or {})
        repo_toon = json_to_toon(repo_metadata, "repository_metadata")
        user_toon = json_to_toon(user_context or {}, "user_context")
        repo_toon_is_flat = is_flat_toon(repo_toon)
        user_toon_is_flat = is_flat_toon(user_toon)
        
        prompt = f"""You are a Persona Router for a repository intelligence system.
Based on the following repository metadata and user context, classify this interaction 
into exactly ONE of these modes:

1. SOLO_DEV — Individual developer exploring/onboarding onto a codebase
2. STARTUP — Team assessing business risk, velocity blockers, ownership gaps
3. ENTERPRISE — Large org needing governance, compliance, audit trails
4. OSS_MAINTAINER — Open source maintainer focused on contributor onboarding

Step 1: JSON converted to linear key=value (no nesting)
Repository metadata (linear):
{repo_linear}

User context (linear):
{user_linear}

Step 2: Linear representation converted to flat TOON (no nesting/indentation)
Repository metadata (TOON, flat={repo_toon_is_flat}):
{repo_toon}

User context (TOON, flat={user_toon_is_flat}):
{user_toon}

Respond in JSON:
{{
    "persona_mode": "SOLO_DEV|STARTUP|ENTERPRISE|OSS_MAINTAINER",
    "confidence": 0.0-1.0,
    "reasoning": ["reason1", "reason2"]
}}"""

        if not self.client:
            self.emit_progress("Groq client unavailable, defaulting to SOLO_DEV")
            return {
                "persona_mode": "SOLO_DEV",
                "confidence": 0.50,
                "reasoning": ["Groq not available, using default"],
                "weights": PERSONA_WEIGHTS["SOLO_DEV"]
            }

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You classify repository analysis requests into persona modes. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                model=settings.GROQ_MODEL,
                temperature=0.1,
                max_tokens=300
            )
            
            text = response.choices[0].message.content
            start = text.find('{')
            end = text.rfind('}') + 1
            result = json.loads(text[start:end])
            
            mode = result.get("persona_mode", "SOLO_DEV")
            if mode not in PERSONA_WEIGHTS:
                mode = "SOLO_DEV"
            
            result["persona_mode"] = mode
            result["weights"] = PERSONA_WEIGHTS[mode]
            
            self.emit_progress(
                f"Persona classified (LLM): {mode}",
                {"confidence": result.get("confidence", 0.7)}
            )
            return result
            
        except Exception as e:
            self.emit_progress(f"LLM classification failed: {e}, defaulting to SOLO_DEV")
            return {
                "persona_mode": "SOLO_DEV",
                "confidence": 0.50,
                "reasoning": ["Classification failed, using default"],
                "weights": PERSONA_WEIGHTS["SOLO_DEV"]
            }
