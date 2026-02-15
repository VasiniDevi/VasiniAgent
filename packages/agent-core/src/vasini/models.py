"""Pydantic v2 models for all 7 composable layers + AgentConfig."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Soul Layer ──────────────────────────────────────────────────────────────


class SoulIdentity(BaseModel):
    name: str
    language: str = "en"
    languages: list[str] = Field(default_factory=list)


class SoulPersonality(BaseModel):
    communication_style: str = "professional"
    verbosity: str = "concise"
    proactivity: str = "proactive"
    confidence_expression: str = "balanced"


class SoulTone(BaseModel):
    default: str = ""
    on_success: str = ""
    on_error: str = ""
    on_uncertainty: str = ""


class SoulAdaptations(BaseModel):
    beginner_user: str = ""
    expert_user: str = ""
    crisis_mode: str = ""


class Soul(BaseModel):
    schema_version: str = "1.0"
    identity: SoulIdentity = Field(default_factory=SoulIdentity)
    personality: SoulPersonality = Field(default_factory=SoulPersonality)
    tone: SoulTone = Field(default_factory=SoulTone)
    principles: list[str] = Field(default_factory=list)
    adaptations: SoulAdaptations = Field(default_factory=SoulAdaptations)


# ── Role Layer ──────────────────────────────────────────────────────────────


class RoleGoal(BaseModel):
    primary: str = ""
    secondary: list[str] = Field(default_factory=list)


class SkillMetric(BaseModel):
    name: str
    target: float | int | str


class CompetencySkill(BaseModel):
    id: str
    name: str
    level: str = "proficient"
    evidence: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    metrics: list[SkillMetric] = Field(default_factory=list)


class CompetencyGraph(BaseModel):
    skills: list[CompetencySkill] = Field(default_factory=list)


class Role(BaseModel):
    schema_version: str = "1.0"
    title: str = ""
    domain: str = ""
    seniority: str = ""
    goal: RoleGoal = Field(default_factory=RoleGoal)
    backstory: str = ""
    competency_graph: CompetencyGraph = Field(default_factory=CompetencyGraph)
    domain_knowledge: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# ── Tools Layer ─────────────────────────────────────────────────────────────


class ToolSandbox(BaseModel):
    timeout: int = 30
    memory: str = ""
    cpu: float | None = None
    network: str = "none"
    filesystem: str = "scoped"
    egress_allowlist: list[str] = Field(default_factory=list)
    scoped_paths: list[str] = Field(default_factory=list)


class ToolDef(BaseModel):
    id: str
    name: str
    description: str = ""
    sandbox: ToolSandbox = Field(default_factory=ToolSandbox)
    risk_level: str = "low"
    requires_approval: bool = False
    audit: bool = True


class ToolPolicy(BaseModel):
    rate_limit: int | None = None
    max_retries: int | None = None


class ToolPolicies(BaseModel):
    max_concurrent: int | None = None
    max_calls_per_task: int | None = None
    cost_limit_per_task: float | None = None


class Tools(BaseModel):
    schema_version: str = "1.0"
    available: list[ToolDef] = Field(default_factory=list)
    denied: list[str] = Field(default_factory=list)
    tool_policies: dict[str, ToolPolicy] = Field(default_factory=dict)


# ── Skill Layer ─────────────────────────────────────────────────────────────


class Skill(BaseModel):
    id: str
    name: str
    description: str = ""
    trigger: str = ""
    required_tools: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    estimated_duration: str = ""
    body: str = ""


# ── Guardrails Layer ────────────────────────────────────────────────────────


class PIIDetection(BaseModel):
    enabled: bool = False
    action: str = "warn"


class InputGuardrails(BaseModel):
    max_length: int = 50000
    sanitization: bool = True
    jailbreak_detection: bool = True
    pii_detection: PIIDetection = Field(default_factory=PIIDetection)


class HallucinationCheck(BaseModel):
    enabled: bool = False
    confidence_threshold: float = 0.80


class OutputGuardrails(BaseModel):
    max_length: int = 100000
    pii_check: bool = True
    hallucination_check: HallucinationCheck = Field(default_factory=HallucinationCheck)
    source_citation_required: bool = False


class BehavioralGuardrails(BaseModel):
    prohibited_actions: list[str] = Field(default_factory=list)
    required_disclaimers: list[str] = Field(default_factory=list)
    escalation_triggers: list[str] = Field(default_factory=list)
    max_autonomous_steps: int = 10


class Compliance(BaseModel):
    audit_logging: bool = True
    data_retention: str = "90d"


class Guardrails(BaseModel):
    schema_version: str = "1.0"
    input: InputGuardrails = Field(default_factory=InputGuardrails)
    output: OutputGuardrails = Field(default_factory=OutputGuardrails)
    behavioral: BehavioralGuardrails = Field(default_factory=BehavioralGuardrails)
    compliance: Compliance = Field(default_factory=Compliance)


# ── Memory Layer ────────────────────────────────────────────────────────────


class ShortTermMemory(BaseModel):
    enabled: bool = True
    ttl: str = "24h"
    max_entries: int = 100


class EpisodicMemory(BaseModel):
    enabled: bool = True
    confidence_threshold: float = 0.75
    retrieval_top_k: int = 10
    similarity_threshold: float = 0.7
    source_required: bool = True


class FactualMemory(BaseModel):
    enabled: bool = True


class CrossSessionMemory(BaseModel):
    enabled: bool = True
    merge_strategy: str = "highest_confidence"


class Memory(BaseModel):
    schema_version: str = "1.0"
    short_term: ShortTermMemory = Field(default_factory=ShortTermMemory)
    episodic: EpisodicMemory = Field(default_factory=EpisodicMemory)
    factual: FactualMemory = Field(default_factory=FactualMemory)
    cross_session: CrossSessionMemory = Field(default_factory=CrossSessionMemory)


# ── Workflow Layer ──────────────────────────────────────────────────────────


class SOPStep(BaseModel):
    id: str
    action: str
    tool: str | None = None
    on_success: str | None = None
    on_failure: str | None = None
    timeout: int | None = None


class SOP(BaseModel):
    id: str
    name: str
    trigger: str = ""
    steps: list[SOPStep] = Field(default_factory=list)


class Handoff(BaseModel):
    from_: str = Field(default="", alias="from")
    to: str = ""
    condition: str = ""
    context_transfer: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class Reporting(BaseModel):
    format: str = "structured"


class Workflow(BaseModel):
    schema_version: str = "1.0"
    default_process: str = "adaptive"
    sop: list[SOP] = Field(default_factory=list)
    handoffs: list[Handoff] = Field(default_factory=list)
    reporting: Reporting = Field(default_factory=Reporting)


# ── AgentConfig (assembled) ────────────────────────────────────────────────


class AgentConfig(BaseModel):
    pack_id: str
    version: str = "1.0.0"
    risk_level: str = "medium"
    soul: Soul = Field(default_factory=Soul)
    role: Role = Field(default_factory=Role)
    tools: Tools = Field(default_factory=Tools)
    skills: list[Skill] = Field(default_factory=list)
    guardrails: Guardrails = Field(default_factory=Guardrails)
    memory: Memory = Field(default_factory=Memory)
    workflow: Workflow = Field(default_factory=Workflow)
