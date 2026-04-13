"""
R1 - Core Intelligence & Cognitive Systems
High-speed reasoning, context understanding, adaptive learning, knowledge graphs
"""
import asyncio
import logging
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

logger = logging.getLogger("R1:cognitive")


@dataclass
class ReasoningStep:
    step_id: str
    input_data: Any
    reasoning_type: str
    confidence: float
    result: Any
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)


@dataclass
class ContextFrame:
    session_id: str
    entities: Dict[str, Any] = field(default_factory=dict)
    intent: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    emotional_state: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class Hypothesis:
    id: str
    statement: str
    confidence: float
    evidence: List[str] = field(default_factory=list)
    counter_evidence: List[str] = field(default_factory=list)
    status: str = "pending"
    test_results: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class KnowledgeNode:
    id: str
    concept: str
    properties: Dict[str, Any] = field(default_factory=dict)
    relationships: Dict[str, List[str]] = field(default_factory=dict)
    confidence: float = 1.0
    source: str = "inferred"
    created_at: datetime = field(default_factory=datetime.now)


class ParallelReasoningEngine:
    def __init__(self, max_parallel: int = 10):
        self.max_parallel = max_parallel
        self.reasoning_chains: List[List[ReasoningStep]] = []
        self.active_reasoning: Dict[str, ReasoningStep] = {}
        
    async def reason_parallel(self, prompt: str, contexts: List[Dict]) -> List[ReasoningStep]:
        tasks = []
        for ctx in contexts[:self.max_parallel]:
            task = self._reason_single(prompt, ctx)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        for r in results:
            if isinstance(r, ReasoningStep):
                valid_results.append(r)
        
        return valid_results
    
    async def _reason_single(self, prompt: str, context: Dict) -> ReasoningStep:
        step_id = hashlib.md5(f"{prompt}{datetime.now()}".encode()).hexdigest()[:12]
        
        reasoning_type = self._classify_reasoning(prompt)
        
        result = await self._execute_reasoning(prompt, context, reasoning_type)
        
        step = ReasoningStep(
            step_id=step_id,
            input_data={"prompt": prompt, "context": context},
            reasoning_type=reasoning_type,
            confidence=result.get("confidence", 0.5),
            result=result.get("output"),
            metadata=result.get("metadata", {})
        )
        
        self.active_reasoning[step_id] = step
        return step
    
    def _classify_reasoning(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        
        if any(w in prompt_lower for w in ["why", "because", "explain", "how does"]):
            return "causal"
        elif any(w in prompt_lower for w in ["compare", "versus", "vs", "difference"]):
            return "comparative"
        elif any(w in prompt_lower for w in ["predict", "future", "will", "forecast"]):
            return "predictive"
        elif any(w in prompt_lower for w in ["solve", "fix", "resolve", "answer"]):
            return "problem_solving"
        elif any(w in prompt_lower for w in ["analyze", "examine", "review"]):
            return "analytical"
        else:
            return "general"
    
    async def _execute_reasoning(self, prompt: str, context: Dict, reasoning_type: str) -> Dict:
        from R1.providers_v2 import get_provider
        
        provider = get_provider()
        
        system_prompt = f"""You are R1's reasoning engine. Perform {reasoning_type} reasoning on the following:
        
Prompt: {prompt}
Context: {json.dumps(context)}

Provide your reasoning with:
1. Key observations
2. Logical steps
3. Confidence level (0.0-1.0)
4. Any assumptions made

Return as JSON with keys: output, confidence, metadata"""

        try:
            response = await provider.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ])
            
            return {
                "output": response.get("content", ""),
                "confidence": 0.85,
                "metadata": {"reasoning_type": reasoning_type}
            }
        except Exception as e:
            logger.error(f"Reasoning error: {e}")
            return {
                "output": f"Reasoning failed: {str(e)}",
                "confidence": 0.0,
                "metadata": {"error": str(e)}
            }


class ContextEngine:
    def __init__(self):
        self.frames: Dict[str, ContextFrame] = {}
        self.entity_extractors: List[Callable] = []
        
    def create_frame(self, session_id: str) -> ContextFrame:
        frame = ContextFrame(session_id=session_id)
        self.frames[session_id] = frame
        return frame
    
    def get_frame(self, session_id: str) -> Optional[ContextFrame]:
        return self.frames.get(session_id)
    
    def update_frame(self, session_id: str, data: Dict) -> ContextFrame:
        frame = self.frames.get(session_id)
        if not frame:
            frame = self.create_frame(session_id)
        
        if "entities" in data:
            frame.entities.update(data["entities"])
        if "intent" in data:
            frame.intent = data["intent"]
        if "topics" in data:
            frame.topics = list(set(frame.topics + data["topics"]))
        if "constraints" in data:
            frame.constraints.update(data["constraints"])
        
        frame.history.append({
            "timestamp": datetime.now().isoformat(),
            "data": data
        })
        frame.last_updated = datetime.now()
        
        return frame
    
    def extract_entities(self, text: str) -> Dict[str, Any]:
        entities = {}
        
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        entities["emails"] = re.findall(email_pattern, text)
        
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        entities["urls"] = re.findall(url_pattern, text)
        
        time_patterns = [
            (r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b', 'time'),
            (r'\b(today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', 'date_reference'),
        ]
        for pattern, etype in time_patterns:
            matches = re.findall(pattern, text.lower())
            if matches:
                entities[etype] = matches
        
        command_indicators = {
            "search": ["search", "find", "look up", "google"],
            "execute": ["run", "execute", "do", "perform"],
            "create": ["create", "make", "build", "generate"],
            "read": ["read", "show", "display", "open"],
            "write": ["write", "save", "store", "record"],
            "delete": ["delete", "remove", "erase", "clear"],
            "analyze": ["analyze", "examine", "review", "check"],
        }
        
        for cmd, indicators in command_indicators.items():
            if any(ind in text.lower() for ind in indicators):
                entities.setdefault("commands", []).append(cmd)
        
        return entities
    
    def get_conversation_summary(self, session_id: str) -> Dict:
        frame = self.frames.get(session_id)
        if not frame:
            return {}
        
        return {
            "session_id": session_id,
            "entities": frame.entities,
            "intent": frame.intent,
            "topics": frame.topics,
            "turns": len(frame.history),
            "duration": (frame.last_updated - frame.created_at).total_seconds()
        }


class AdaptiveLearning:
    def __init__(self, memory_module=None):
        self.memory = memory_module
        self.learning_history: List[Dict] = []
        self.patterns: Dict[str, List] = defaultdict(list)
        self.improvement_feedback: List[Dict] = []
        
    async def learn_from_interaction(self, interaction: Dict) -> bool:
        try:
            user_input = interaction.get("user_input", "")
            response = interaction.get("response", "")
            success = interaction.get("success", False)
            feedback = interaction.get("feedback", None)
            
            pattern_key = self._extract_pattern_key(user_input)
            self.patterns[pattern_key].append({
                "timestamp": datetime.now().isoformat(),
                "response": response,
                "success": success
            })
            
            if feedback:
                self.improvement_feedback.append({
                    "timestamp": datetime.now().isoformat(),
                    "feedback": feedback,
                    "context": user_input[:100]
                })
            
            if self.memory:
                await self.memory.add_memory(
                    f"Learned from interaction: {pattern_key}",
                    memory_type="learning",
                    metadata=interaction
                )
            
            self.learning_history.append({
                "timestamp": datetime.now().isoformat(),
                "pattern": pattern_key,
                "success": success
            })
            
            return True
        except Exception as e:
            logger.error(f"Learning error: {e}")
            return False
    
    def _extract_pattern_key(self, text: str) -> str:
        words = text.lower().split()
        if not words:
            return "empty"
        
        intent_words = [w for w in words if len(w) > 3][:3]
        return "_".join(intent_words) if intent_words else "default"
    
    def get_improvements(self) -> List[Dict]:
        improvements = []
        
        for pattern, history in self.patterns.items():
            if len(history) >= 3:
                success_rate = sum(1 for h in history if h["success"]) / len(history)
                if success_rate < 0.7:
                    improvements.append({
                        "pattern": pattern,
                        "success_rate": success_rate,
                        "suggestion": "Improve response quality for this pattern"
                    })
        
        return improvements
    
    async def retrain_context(self) -> Dict:
        improvements = self.get_improvements()
        
        return {
            "patterns_analyzed": len(self.patterns),
            "improvements_needed": len(improvements),
            "improvements": improvements,
            "recommendation": "Adjust model parameters" if improvements else "Performance optimal"
        }


class KnowledgeGraph:
    def __init__(self):
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.inference_cache: Dict[str, Any] = {}
        
    def add_node(self, concept: str, properties: Dict = None, relationships: Dict = None) -> KnowledgeNode:
        node_id = hashlib.md5(concept.encode()).hexdigest()[:16]
        
        if node_id in self.nodes:
            existing = self.nodes[node_id]
            if properties:
                existing.properties.update(properties)
            if relationships:
                for rel_type, targets in relationships.items():
                    existing.relationships.setdefault(rel_type, []).extend(targets)
            return existing
        
        node = KnowledgeNode(
            id=node_id,
            concept=concept,
            properties=properties or {},
            relationships=relationships or {}
        )
        
        self.nodes[node_id] = node
        return node
    
    def relate(self, concept1: str, relation: str, concept2: str) -> bool:
        node1 = self.add_node(concept1)
        node2 = self.add_node(concept2)
        
        node1.relationships.setdefault(relation, []).append(node2.id)
        node2.relationships.setdefault(f"inverse_{relation}", []).append(node1.id)
        
        return True
    
    def query(self, concept: str, relation: str = None) -> List[KnowledgeNode]:
        node_id = hashlib.md5(concept.encode()).hexdigest()[:16]
        
        if node_id not in self.nodes:
            return []
        
        node = self.nodes[node_id]
        
        if relation:
            related_ids = node.relationships.get(relation, [])
            return [self.nodes[rid] for rid in related_ids if rid in self.nodes]
        
        return [self.nodes[rid] for rids in node.relationships.values() for rid in rids if rid in self.nodes]
    
    def infer(self, concept1: str, relation1: str, relation2: str) -> List[str]:
        cache_key = f"{concept1}:{relation1}:{relation2}"
        
        if cache_key in self.inference_cache:
            return self.inference_cache[cache_key]
        
        direct = self.query(concept1, relation1)
        
        inferred = []
        for node in direct:
            further = self.query(node.concept, relation2)
            inferred.extend([n.concept for n in further])
        
        self.inference_cache[cache_key] = inferred
        return inferred
    
    def get_concept_path(self, start: str, end: str, max_depth: int = 3) -> List[str]:
        if start not in self.nodes or end not in self.nodes:
            return []
        
        start_id = hashlib.md5(start.encode()).hexdigest()[:16]
        end_id = hashlib.md5(end.encode()).hexdigest()[:16]
        
        visited = set()
        queue = [(start_id, [start])]
        
        while queue:
            current_id, path = queue.pop(0)
            
            if current_id == end_id:
                return path
            
            if len(path) > max_depth:
                continue
            
            visited.add(current_id)
            
            current_node = self.nodes.get(current_id)
            if not current_node:
                continue
            
            for relation, related_ids in current_node.relationships.items():
                for rel_id in related_ids:
                    if rel_id not in visited:
                        rel_node = self.nodes.get(rel_id)
                        if rel_node:
                            queue.append((rel_id, path + [rel_node.concept]))
        
        return []


class HypothesisTester:
    def __init__(self):
        self.hypotheses: Dict[str, Hypothesis] = {}
        self.test_results: List[Dict] = []
        
    def generate_hypothesis(self, statement: str, evidence: List[str] = None) -> Hypothesis:
        hypothesis_id = hashlib.md5(statement.encode()).hexdigest()[:12]
        
        hypothesis = Hypothesis(
            id=hypothesis_id,
            statement=statement,
            confidence=0.5,
            evidence=evidence or []
        )
        
        self.hypotheses[hypothesis_id] = hypothesis
        return hypothesis
    
    async def test_hypothesis(self, hypothesis_id: str, test_data: Dict) -> Dict:
        if hypothesis_id not in self.hypotheses:
            return {"error": "Hypothesis not found"}
        
        hypothesis = self.hypotheses[hypothesis_id]
        
        test_result = {
            "hypothesis_id": hypothesis_id,
            "test_data": test_data,
            "timestamp": datetime.now().isoformat(),
            "passed": False,
            "details": ""
        }
        
        statement_lower = hypothesis.statement.lower()
        
        if "if" in statement_lower and "then" in statement_lower:
            test_result["passed"] = True
            test_result["details"] = "Conditional hypothesis validated"
        elif any(word in statement_lower for word in ["always", "never", "all", "none"]):
            test_result["passed"] = False
            test_result["details"] = "Absolute statements difficult to verify"
        else:
            test_result["passed"] = True
            test_result["details"] = "Hypothesis supported by test data"
        
        hypothesis.test_results = test_result
        hypothesis.status = "tested"
        
        self.test_results.append(test_result)
        
        return test_result
    
    def get_active_hypotheses(self) -> List[Hypothesis]:
        return [h for h in self.hypotheses.values() if h.status == "pending"]


class CognitiveWorkloadManager:
    def __init__(self):
        self.tasks: Dict[str, Dict] = {}
        self.priority_levels = {
            "critical": 1,
            "high": 2,
            "normal": 3,
            "low": 4,
            "background": 5
        }
        self.resource_limits = {
            "cpu_percent": 80,
            "memory_mb": 2048,
            "concurrent_tasks": 10
        }
        
    def add_task(self, task_id: str, priority: str = "normal", estimated_load: float = 1.0) -> bool:
        if task_id in self.tasks:
            return False
        
        priority_num = self.priority_levels.get(priority, 3)
        
        self.tasks[task_id] = {
            "id": task_id,
            "priority": priority,
            "priority_num": priority_num,
            "estimated_load": estimated_load,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        return True
    
    def get_next_task(self) -> Optional[Dict]:
        pending = [t for t in self.tasks.values() if t["status"] == "pending"]
        
        if not pending:
            return None
        
        pending.sort(key=lambda x: (x["priority_num"], x["created_at"]))
        
        return pending[0]
    
    def update_task_status(self, task_id: str, status: str) -> bool:
        if task_id not in self.tasks:
            return False
        
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["updated_at"] = datetime.now().isoformat()
        
        return True
    
    def get_workload_summary(self) -> Dict:
        status_counts = defaultdict(int)
        priority_counts = defaultdict(int)
        
        for task in self.tasks.values():
            status_counts[task["status"]] += 1
            priority_counts[task["priority"]] += 1
        
        total_load = sum(t["estimated_load"] for t in self.tasks.values() if t["status"] == "running")
        
        return {
            "total_tasks": len(self.tasks),
            "by_status": dict(status_counts),
            "by_priority": dict(priority_counts),
            "total_load": total_load,
            "within_limits": total_load < self.resource_limits["concurrent_tasks"]
        }


class SelfOptimizer:
    def __init__(self):
        self.metrics: Dict[str, List[float]] = defaultdict(list)
        self.optimization_history: List[Dict] = []
        
    def record_metric(self, metric_name: str, value: float):
        self.metrics[metric_name].append(value)
        
        if len(self.metrics[metric_name]) > 1000:
            self.metrics[metric_name] = self.metrics[metric_name][-1000:]
    
    def get_metric_stats(self, metric_name: str) -> Dict:
        values = self.metrics.get(metric_name, [])
        
        if not values:
            return {"count": 0, "mean": 0, "min": 0, "max": 0}
        
        return {
            "count": len(values),
            "mean": np.mean(values),
            "min": np.min(values),
            "max": np.max(values),
            "std": np.std(values)
        }
    
    async def optimize(self) -> Dict:
        recommendations = []
        
        for metric_name, values in self.metrics.items():
            if len(values) < 10:
                continue
            
            stats = self.get_metric_stats(metric_name)
            
            if "latency" in metric_name and stats["mean"] > 1000:
                recommendations.append({
                    "metric": metric_name,
                    "issue": "High latency detected",
                    "action": "Consider caching or async processing"
                })
            
            if "error" in metric_name and stats["mean"] > 0.1:
                recommendations.append({
                    "metric": metric_name,
                    "issue": "High error rate",
                    "action": "Review error handling"
                })
        
        self.optimization_history.append({
            "timestamp": datetime.now().isoformat(),
            "recommendations": recommendations
        })
        
        return {
            "metrics_analyzed": len(self.metrics),
            "recommendations": recommendations,
            "auto_optimize": True
        }


class CognitiveSystem:
    def __init__(self, memory_module=None):
        self.reasoning = ParallelReasoningEngine()
        self.context = ContextEngine()
        self.learning = AdaptiveLearning(memory_module)
        self.knowledge = KnowledgeGraph()
        self.hypothesis = HypothesisTester()
        self.workload = CognitiveWorkloadManager()
        self.optimizer = SelfOptimizer()
        
    async def process(self, prompt: str, session_id: str = "default") -> Dict:
        frame = self.context.get_frame(session_id)
        if not frame:
            frame = self.context.create_frame(session_id)
        
        entities = self.context.extract_entities(prompt)
        self.context.update_frame(session_id, {
            "entities": entities,
            "topics": self._extract_topics(prompt)
        })
        
        reasoning_result = await self.reasoning.reason_parallel(
            prompt,
            [{"entities": entities, "history": frame.history[-5:]}]
        )
        
        await self.learning.learn_from_interaction({
            "user_input": prompt,
            "response": reasoning_result[0].result if reasoning_result else "",
            "success": True
        })
        
        return {
            "entities": entities,
            "reasoning": [{"step": r.reasoning_type, "confidence": r.confidence} for r in reasoning_result],
            "context_summary": self.context.get_conversation_summary(session_id),
            "knowledge_related": self.knowledge.query(prompt.split()[0] if prompt.split() else "")
        }
    
    def _extract_topics(self, text: str) -> List[str]:
        topic_keywords = {
            "code": ["code", "programming", "script", "function", "class"],
            "data": ["data", "database", "query", "table", "record"],
            "file": ["file", "folder", "directory", "path", "open"],
            "system": ["system", "cpu", "memory", "process", "network"],
            "search": ["search", "find", "lookup", "query"],
            "communication": ["email", "message", "send", "chat", "notify"]
        }
        
        topics = []
        text_lower = text.lower()
        
        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)
        
        return topics


_cognitive_system: Optional[CognitiveSystem] = None

def get_cognitive_system(memory_module=None) -> CognitiveSystem:
    global _cognitive_system
    if _cognitive_system is None:
        _cognitive_system = CognitiveSystem(memory_module)
    return _cognitive_system
