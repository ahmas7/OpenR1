"""
R1 - Generalized capability registry and execution layer.
"""
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from collections import Counter


@dataclass
class Capability:
    domain: str
    name: str
    slug: str
    status: str
    backing_systems: List[str]
    description: str


def _slugify(value: str) -> str:
    return (
        value.lower()
        .replace("&", "and")
        .replace("/", " ")
        .replace("-", " ")
        .replace(",", " ")
        .replace(".", "")
        .strip()
        .replace(" ", "_")
    )


CAPABILITY_DOMAINS: Dict[str, List[str]] = {
    "cognition": [
        "Multi-step reasoning",
        "Goal decomposition",
        "Task planning engine",
        "Context awareness",
        "Adaptive learning from feedback",
        "Long-term memory storage",
        "Short-term working memory",
        "Decision optimization",
        "Probabilistic reasoning",
        "Strategic thinking",
        "Dynamic problem solving",
        "Pattern recognition",
        "Predictive modeling",
        "Knowledge graph reasoning",
        "Multi-modal reasoning",
    ],
    "autonomous_execution": [
        "Autonomous task creation",
        "Task prioritization",
        "Goal-driven execution loops",
        "Self-correcting workflows",
        "Automatic progress tracking",
        "Background job execution",
        "Parallel task handling",
        "Time-based scheduling",
        "Event-triggered automation",
        "Workflow orchestration",
        "Retry and failure recovery",
        "Continuous monitoring",
        "Task dependency resolution",
        "Task result verification",
        "Autonomous iteration cycles",
    ],
    "computer_control": [
        "Web browsing automation",
        "Software UI interaction",
        "Form filling automation",
        "File system control",
        "Script execution",
        "Command line operations",
        "Application launching",
        "Data extraction from websites",
        "Screenshot interpretation",
        "Mouse and keyboard simulation",
        "Browser tab management",
        "Multi-app workflow automation",
        "Document editing automation",
        "Spreadsheet manipulation",
        "Software testing automation",
    ],
    "research": [
        "Multi-source web research",
        "Academic paper analysis",
        "Market research automation",
        "Competitive intelligence gathering",
        "Trend detection",
        "Fact synthesis",
        "Knowledge summarization",
        "Information validation",
        "Data aggregation",
        "Cross-source correlation",
        "Insight generation",
        "Literature reviews",
        "Industry monitoring",
        "News analysis",
        "Data-driven reporting",
    ],
    "coding": [
        "Code generation",
        "Debugging automation",
        "Refactoring codebases",
        "Test generation",
        "API integration",
        "Code documentation creation",
        "Multi-language programming",
        "Dependency management",
        "Version control interaction",
        "Deployment automation",
        "Infrastructure scripting",
        "Build pipeline creation",
        "Security vulnerability scanning",
        "Performance optimization",
        "Codebase understanding",
    ],
    "data_analysis": [
        "Dataset ingestion",
        "Data cleaning",
        "Statistical analysis",
        "Predictive analytics",
        "Machine learning model usage",
        "Data visualization generation",
        "Dashboard creation",
        "Data pattern discovery",
        "Business intelligence reporting",
        "Data anomaly detection",
        "Forecast modeling",
        "KPI analysis",
        "Time-series analysis",
        "Automated reporting",
        "Insight summarization",
    ],
    "content": [
        "Long-form article writing",
        "Marketing copy creation",
        "Script writing",
        "Technical documentation",
        "Email drafting",
        "Social media content generation",
        "Presentation creation",
        "Speech writing",
        "Translation across languages",
        "Tone adaptation",
        "Content summarization",
        "Dialogue simulation",
        "Brand voice adaptation",
        "Editing and proofreading",
        "Knowledge explanation",
    ],
    "business": [
        "Resume screening",
        "Meeting summarization",
        "Project planning",
        "Task management",
        "CRM data processing",
        "Customer support automation",
        "Proposal generation",
        "Contract analysis",
        "Financial report generation",
        "Sales lead analysis",
    ],
    "multi_agent": [
        "Agent collaboration",
        "Task delegation to sub-agents",
        "Distributed workflow execution",
        "Agent role specialization",
        "Consensus decision making",
    ],
    "self_improvement": [
        "Self-performance monitoring",
        "Adaptive workflow optimization",
        "Error learning loops",
        "Knowledge base expansion",
        "Continuous capability improvement",
    ],
}


DOMAIN_BACKING_SYSTEMS: Dict[str, List[str]] = {
    "cognition": ["cognitive", "memory", "decisions"],
    "autonomous_execution": ["agent", "planning", "cron"],
    "computer_control": ["browser", "system", "code_executor"],
    "research": ["browser", "analytics", "multimodal"],
    "coding": ["code_executor", "system", "skills"],
    "data_analysis": ["analytics", "code_executor", "multimodal"],
    "content": ["providers", "voice", "memory"],
    "business": ["planning", "tools", "analytics"],
    "multi_agent": ["agent", "gateway", "planning"],
    "self_improvement": ["self_improver", "analytics", "diagnostics"],
}


FULLY_AVAILABLE = {
    "multi_step_reasoning",
    "task_planning_engine",
    "context_awareness",
    "adaptive_learning_from_feedback",
    "long_term_memory_storage",
    "short_term_working_memory",
    "pattern_recognition",
    "predictive_modeling",
    "knowledge_graph_reasoning",
    "autonomous_task_creation",
    "task_prioritization",
    "background_job_execution",
    "parallel_task_handling",
    "time_based_scheduling",
    "workflow_orchestration",
    "retry_and_failure_recovery",
    "continuous_monitoring",
    "task_dependency_resolution",
    "web_browsing_automation",
    "form_filling_automation",
    "file_system_control",
    "script_execution",
    "command_line_operations",
    "data_extraction_from_websites",
    "browser_tab_management",
    "multi_source_web_research",
    "trend_detection",
    "knowledge_summarization",
    "data_aggregation",
    "insight_generation",
    "data_driven_reporting",
    "code_generation",
    "api_integration",
    "dependency_management",
    "security_vulnerability_scanning",
    "codebase_understanding",
    "dataset_ingestion",
    "statistical_analysis",
    "predictive_analytics",
    "dashboard_creation",
    "data_pattern_discovery",
    "data_anomaly_detection",
    "forecast_modeling",
    "time_series_analysis",
    "automated_reporting",
    "email_drafting",
    "translation_across_languages",
    "content_summarization",
    "dialogue_simulation",
    "knowledge_explanation",
    "meeting_summarization",
    "project_planning",
    "task_management",
    "agent_collaboration",
    "self_performance_monitoring",
    "adaptive_workflow_optimization",
    "error_learning_loops",
    "continuous_capability_improvement",
}


PARTIAL = {
    "goal_decomposition",
    "decision_optimization",
    "probabilistic_reasoning",
    "strategic_thinking",
    "dynamic_problem_solving",
    "multi_modal_reasoning",
    "goal_driven_execution_loops",
    "self_correcting_workflows",
    "automatic_progress_tracking",
    "event_triggered_automation",
    "task_result_verification",
    "autonomous_iteration_cycles",
    "software_ui_interaction",
    "application_launching",
    "screenshot_interpretation",
    "mouse_and_keyboard_simulation",
    "multi_app_workflow_automation",
    "document_editing_automation",
    "spreadsheet_manipulation",
    "software_testing_automation",
    "academic_paper_analysis",
    "market_research_automation",
    "competitive_intelligence_gathering",
    "fact_synthesis",
    "information_validation",
    "cross_source_correlation",
    "literature_reviews",
    "industry_monitoring",
    "news_analysis",
    "debugging_automation",
    "refactoring_codebases",
    "test_generation",
    "code_documentation_creation",
    "multi_language_programming",
    "version_control_interaction",
    "deployment_automation",
    "infrastructure_scripting",
    "build_pipeline_creation",
    "performance_optimization",
    "data_cleaning",
    "machine_learning_model_usage",
    "data_visualization_generation",
    "business_intelligence_reporting",
    "kpi_analysis",
    "insight_summarization",
    "long_form_article_writing",
    "marketing_copy_creation",
    "script_writing",
    "technical_documentation",
    "social_media_content_generation",
    "presentation_creation",
    "speech_writing",
    "tone_adaptation",
    "brand_voice_adaptation",
    "editing_and_proofreading",
    "resume_screening",
    "crm_data_processing",
    "customer_support_automation",
    "proposal_generation",
    "contract_analysis",
    "financial_report_generation",
    "sales_lead_analysis",
    "task_delegation_to_sub_agents",
    "distributed_workflow_execution",
    "agent_role_specialization",
    "consensus_decision_making",
    "knowledge_base_expansion",
}


def build_registry() -> List[Capability]:
    items: List[Capability] = []
    for domain, names in CAPABILITY_DOMAINS.items():
        for name in names:
            slug = _slugify(name)
            status = "available" if slug in FULLY_AVAILABLE else "partial" if slug in PARTIAL else "planned"
            items.append(
                Capability(
                    domain=domain,
                    name=name,
                    slug=slug,
                    status=status,
                    backing_systems=DOMAIN_BACKING_SYSTEMS.get(domain, []),
                    description=f"{name} capability in the {domain.replace('_', ' ')} domain.",
                )
            )
    return items


REGISTRY = build_registry()


def list_capabilities(domain: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    items = REGISTRY
    if domain:
        items = [item for item in items if item.domain == domain]
    if status:
        items = [item for item in items if item.status == status]
    return [asdict(item) for item in items]


def summarize_capabilities() -> Dict[str, Any]:
    domain_counts = {
        domain: len(names)
        for domain, names in CAPABILITY_DOMAINS.items()
    }
    status_counts = Counter(item.status for item in REGISTRY)
    return {
        "total_capabilities": len(REGISTRY),
        "domains": domain_counts,
        "status_counts": dict(status_counts),
    }
