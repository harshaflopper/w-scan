"""
Gemini 2.5 Pro — true function-calling wound assessment agent.

The agent sees the wound image and decides which metric tools to call.
It reasons through the TIME framework step-by-step before producing
a structured JSON clinical assessment.

This is NOT a simple summarise-these-numbers prompt.
The model controls the tool-call loop autonomously.
"""

from __future__ import annotations
import json
import os
import re
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from scoring.engine import ClinicalScoringEngine

_scorer = ClinicalScoringEngine()

# ─────────────────────────────────────────────────────────────────────────────
# Tool declarations — what the agent can call
# ─────────────────────────────────────────────────────────────────────────────
_TOOLS = [
    Tool(function_declarations=[
        FunctionDeclaration(
            name="get_tissue_breakdown",
            description=(
                "Returns the pixel-level tissue composition percentages "
                "computed by the SegFormer-B2 ML model. Use this first."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        FunctionDeclaration(
            name="get_geometric_metrics",
            description=(
                "Returns calibrated wound geometry: area (cm²), perimeter (cm), "
                "circularity, and axis measurements."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        FunctionDeclaration(
            name="compute_push_score",
            description=(
                "Computes the NPUAP PUSH Tool score (0–17). "
                "Lower is better. Requires tissue breakdown and exudate level."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "exudate": {
                        "type": "string",
                        "enum": ["none", "light", "moderate", "heavy"],
                        "description": "Exudate level observed from the wound image.",
                    }
                },
                "required": ["exudate"],
            },
        ),
        FunctionDeclaration(
            name="compute_resvech_score",
            description=(
                "Computes RESVECH 2.0 wound healing score (0–35, lower = better). "
                "Requires edge assessment and exudate level."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "edges": {
                        "type": "string",
                        "enum": ["closed", "defined", "diffuse", "callous", "undermined"],
                        "description": "Wound edge characterisation from image.",
                    },
                    "exudate": {
                        "type": "string",
                        "enum": ["none", "scarce", "moderate", "abundant", "hemorrhagic"],
                    },
                },
                "required": ["edges", "exudate"],
            },
        ),
        FunctionDeclaration(
            name="run_infection_check",
            description=(
                "Evaluates NERDS (superficial colonisation) and STONES "
                "(deep infection) criteria from computed metrics. "
                "Returns risk level: LOW / MODERATE / HIGH."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        FunctionDeclaration(
            name="get_healing_trend",
            description=(
                "Returns healing velocity (cm²/day), % healing rate, "
                "and trajectory (IMPROVING/STAGNATING/WORSENING) "
                "compared to previous sessions."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        FunctionDeclaration(
            name="get_inflammation_index",
            description=(
                "Returns the periwound erythema index (0–100) computed "
                "using the Wannous et al. (2010) opponent-colour method."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ])
]

_SYSTEM_INSTRUCTION = """You are a clinical wound-care specialist AI.
You have access to tools that return computed wound metrics from validated CV and ML analysis.

Your task: analyze the wound image, call the tools you need, then produce a complete clinical assessment.

Work through this reasoning sequence:
1. Call get_tissue_breakdown — understand what tissues are present.
2. Call get_geometric_metrics — understand wound size and shape.
3. Call get_inflammation_index — assess periwound erythema.
4. Based on image observations, call compute_push_score and compute_resvech_score.
5. Call run_infection_check.
6. Call get_healing_trend if any history exists.
7. Synthesise findings through the TIME framework:
   T = Tissue (what type dominates, is debridement needed?)
   I = Infection/Inflammation (NERDS/STONES criteria met?)
   M = Moisture (dry/balanced/wet/macerated — from image)
   E = Edge (advancing, stalled, rolled?)

Return your final answer as valid JSON only — no markdown fences, no commentary outside JSON:
{
  "healing_phase": "Inflammatory|Proliferative|Remodeling|Unknown",
  "TIME": {
    "T": "<tissue assessment>",
    "I": "<infection/inflammation assessment>",
    "M": "<moisture assessment>",
    "E": "<edge advancement assessment>"
  },
  "push_score": <int>,
  "resvech_score": <int>,
  "composite_healing_score": <0-100 float>,
  "infection_risk": {
    "level": "LOW|MODERATE|HIGH",
    "NERDS_score": <int>,
    "STONES_score": <int>,
    "active_flags": [<strings>]
  },
  "healing_trajectory": "IMPROVING|STAGNATING|WORSENING|FIRST_SESSION",
  "estimated_closure_days": <int or null>,
  "clinical_summary": "<2-3 sentence expert summary>",
  "recommendations": ["<string>", ...],
  "red_flags": ["<urgent concern if any>"]
}"""


class WoundAgent:
    """
    Gemini 2.5 Pro function-calling agent for wound assessment.

    computed_metrics: all CV/ML outputs from the analysis pipeline,
                      keyed as expected by _handle_tool().
    """

    def __init__(self, computed_metrics: dict):
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self.metrics = computed_metrics
        self.scorer  = _scorer
        self.model   = genai.GenerativeModel(
            model_name="gemini-2.5-pro",
            system_instruction=_SYSTEM_INSTRUCTION,
            tools=_TOOLS,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Tool handler
    # ─────────────────────────────────────────────────────────────────────────
    def _handle_tool(self, name: str, args: dict) -> dict:
        m = self.metrics

        if name == "get_tissue_breakdown":
            return {
                k: m.get(k, 0.0)
                for k in ["granulation_pct", "slough_pct", "necrotic_pct", "epithelial_pct"]
            }

        if name == "get_geometric_metrics":
            return {
                k: m.get(k, 0.0)
                for k in ["area_cm2", "perimeter_cm", "circularity",
                          "longest_axis_cm", "shortest_axis_cm"]
            }

        if name == "compute_push_score":
            exudate = args.get("exudate", "light")
            dominant = m.get("dominant_tissue", "granulation")
            score = self.scorer.push_score(m.get("area_cm2", 0), exudate, dominant)
            return {"push_score": score}

        if name == "compute_resvech_score":
            edges   = args.get("edges", "diffuse")
            exudate = args.get("exudate", "moderate")
            score   = self.scorer.resvech_score(
                area_cm2=m.get("area_cm2", 0),
                edges=edges,
                tissue_pct=m,
                exudate=exudate,
                infection_flag_count=0,
            )
            return {"resvech_score": score}

        if name == "run_infection_check":
            return self.scorer.infection_risk(m)

        if name == "get_healing_trend":
            return {
                "healing_velocity":   m.get("healing_velocity", 0.0),
                "healing_rate_pct":   m.get("healing_rate_pct", None),
                "trajectory":         m.get("trajectory", "FIRST_SESSION"),
                "estimated_closure":  m.get("estimated_closure_days", None),
            }

        if name == "get_inflammation_index":
            return {
                "inflammation_index": m.get("inflammation_index", 0.0),
                "erythema_mean":      m.get("erythema_mean", 0.0),
            }

        return {"error": f"Unknown tool: {name}"}

    # ─────────────────────────────────────────────────────────────────────────
    # Agentic run loop
    # ─────────────────────────────────────────────────────────────────────────
    def run(self, pil_image) -> dict:
        """
        Run the agentic loop:
        1. Send wound image + instruction.
        2. Handle every tool call the model makes.
        3. Return parsed JSON assessment.
        """
        from google.generativeai import protos

        chat = self.model.start_chat()
        response = chat.send_message(
            [
                "Analyze this wound image and produce a complete clinical assessment using your tools.",
                pil_image,
            ]
        )

        # Agentic tool-call loop — keep running until model stops calling tools
        max_iterations = 10
        iterations = 0
        while iterations < max_iterations:
            iterations += 1
            # Check if response contains function calls
            has_function_call = False
            for part in response.candidates[0].content.parts:
                if part.function_call.name:
                    has_function_call = True
                    fc = part.function_call
                    tool_result = self._handle_tool(
                        fc.name,
                        dict(fc.args) if fc.args else {},
                    )
                    response = chat.send_message(
                        protos.Content(
                            parts=[
                                protos.Part(
                                    function_response=protos.FunctionResponse(
                                        name=fc.name,
                                        response={"result": tool_result},
                                    )
                                )
                            ]
                        )
                    )
                    break  # handle one tool call per iteration

            if not has_function_call:
                break  # model returned final text response

        # Extract final text and parse JSON
        final_text = ""
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                final_text += part.text

        return self._parse_json(final_text)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Extract JSON from model output, even if wrapped in markdown."""
        text = text.strip()
        # Strip markdown fences if present
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        if match:
            text = match.group(1)
        # Find JSON object
        match = re.search(r"\{[\s\S]+\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {
            "error": "Model returned non-JSON output",
            "raw": text[:500],
        }
