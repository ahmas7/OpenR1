"""
R1 - Predictive Analytics & Threat Detection Systems
Risk modeling, anomaly detection, forecasting, early warning
"""
import asyncio
import logging
import json
import hashlib
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict
import random

logger = logging.getLogger("R1:analytics")


class RiskLevel(Enum):
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(Enum):
    BEHAVIORAL = "behavioral"
    TEMPORAL = "temporal"
    STATISTICAL = "statistical"
    CONTEXTUAL = "contextual"


@dataclass
class RiskAssessment:
    id: str
    timestamp: datetime
    risk_type: str
    level: RiskLevel
    probability: float
    impact: float
    factors: List[str] = field(default_factory=list)
    mitigation: List[str] = field(default_factory=list)
    status: str = "active"


@dataclass
class Anomaly:
    id: str
    timestamp: datetime
    anomaly_type: AnomalyType
    description: str
    severity: float
    metrics: Dict[str, float] = field(default_factory=dict)
    context: Dict = field(default_factory=dict)
    resolved: bool = False


@dataclass
class Forecast:
    id: str
    target_metric: str
    predicted_value: float
    confidence: float
    time_horizon: timedelta
    model_type: str
    factors: List[str] = field(default_factory=list)


class RiskProbabilityModel:
    def __init__(self):
        self.risk_history: List[RiskAssessment] = []
        self.risk_factors: Dict[str, List[float]] = defaultdict(list)
        self.baseline_metrics: Dict[str, float] = {}
        
    def assess_risk(self, risk_type: str, factors: Dict[str, Any]) -> RiskAssessment:
        probability = 0.0
        impact = 0.0
        factor_list = []
        
        for factor_name, factor_data in factors.items():
            weight = factor_data.get("weight", 0.5)
            value = factor_data.get("value", 0)
            
            probability += value * weight
            factor_list.append(factor_name)
            
            self.risk_factors[factor_name].append(value)
        
        probability = min(1.0, probability)
        
        if probability >= 0.8:
            level = RiskLevel.CRITICAL
        elif probability >= 0.6:
            level = RiskLevel.HIGH
        elif probability >= 0.4:
            level = RiskLevel.MEDIUM
        elif probability >= 0.2:
            level = RiskLevel.LOW
        else:
            level = RiskLevel.MINIMAL
        
        impact = probability * factor_data.get("severity", 1.0)
        
        mitigation = self._generate_mitigation(risk_type, level)
        
        assessment = RiskAssessment(
            id=hashlib.md5(f"{risk_type}{datetime.now()}".encode()).hexdigest()[:12],
            timestamp=datetime.now(),
            risk_type=risk_type,
            level=level,
            probability=probability,
            impact=impact,
            factors=factor_list,
            mitigation=mitigation
        )
        
        self.risk_history.append(assessment)
        
        return assessment
    
    def _generate_mitigation(self, risk_type: str, level: RiskLevel) -> List[str]:
        mitigations = {
            "security": [
                "Enable multi-factor authentication",
                "Review access logs",
                "Update security patches"
            ],
            "operational": [
                "Review backup procedures",
                "Check system redundancy",
                "Test failover systems"
            ],
            "financial": [
                "Review budget allocations",
                "Diversify investments",
                "Increase cash reserves"
            ],
            "compliance": [
                "Schedule audit review",
                "Update documentation",
                "Train staff on regulations"
            ]
        }
        
        base_mitigations = mitigations.get(risk_type, ["Monitor situation"])
        
        if level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            return ["IMMEDIATE ACTION: " + base_mitigations[0]] + base_mitigations[1:]
        
        return base_mitigations[:2]
    
    def get_risk_summary(self) -> Dict:
        if not self.risk_history:
            return {"total_assessments": 0, "active_risks": 0}
        
        by_level = defaultdict(int)
        by_type = defaultdict(int)
        
        active = [r for r in self.risk_history if r.status == "active"]
        
        for r in self.risk_history:
            by_level[r.level] += 1
            by_type[r.risk_type] += 1
        
        return {
            "total_assessments": len(self.risk_history),
            "active_risks": len(active),
            "by_level": {k.value: v for k, v in by_level.items()},
            "by_type": dict(by_type),
            "critical_count": by_level[RiskLevel.CRITICAL],
            "high_count": by_level[RiskLevel.HIGH]
        }


class AnomalyDetection:
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.anomalies: List[Anomaly] = []
        self.baselines: Dict[str, Dict] = {}
        
    def add_data_point(self, metric_name: str, value: float, timestamp: datetime = None):
        if timestamp is None:
            timestamp = datetime.now()
        
        self.metrics[metric_name].append({
            "value": value,
            "timestamp": timestamp
        })
        
        if len(self.metrics[metric_name]) >= 10:
            self._update_baseline(metric_name)
            
            if self._is_anomaly(metric_name, value):
                anomaly = self._create_anomaly(metric_name, value)
                self.anomalies.append(anomaly)
    
    def _update_baseline(self, metric_name: str):
        values = [d["value"] for d in self.metrics[metric_name]]
        
        self.baselines[metric_name] = {
            "mean": statistics.mean(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values)
        }
    
    def _is_anomaly(self, metric_name: str, value: float) -> bool:
        if metric_name not in self.baselines:
            return False
        
        baseline = self.baselines[metric_name]
        
        if baseline["stdev"] == 0:
            return abs(value - baseline["mean"]) > baseline["mean"] * 0.5
        
        z_score = abs(value - baseline["mean"]) / baseline["stdev"]
        
        return z_score > 3.0
    
    def _create_anomaly(self, metric_name: str, value: float) -> Anomaly:
        baseline = self.baselines.get(metric_name, {})
        
        z_score = 0
        if baseline.get("stdev", 0) > 0:
            z_score = abs(value - baseline.get("mean", 0)) / baseline["stdev"]
        
        return Anomaly(
            id=hashlib.md5(f"{metric_name}{value}{datetime.now()}".encode()).hexdigest()[:12],
            timestamp=datetime.now(),
            anomaly_type=AnomalyType.STATISTICAL,
            description=f"Anomaly detected in {metric_name}: {value} (z-score: {z_score:.2f})",
            severity=min(1.0, z_score / 5.0),
            metrics={metric_name: value, "z_score": z_score},
            context={"baseline": baseline}
        )
    
    def get_active_anomalies(self) -> List[Anomaly]:
        return [a for a in self.anomalies if not a.resolved]
    
    def resolve_anomaly(self, anomaly_id: str) -> bool:
        for anomaly in self.anomalies:
            if anomaly.id == anomaly_id:
                anomaly.resolved = True
                return True
        return False
    
    def detect_behavioral_anomaly(self, entity_id: str, events: List[Dict]) -> Optional[Anomaly]:
        if len(events) < 5:
            return None
        
        recent_events = events[-5:]
        event_types = [e.get("type") for e in recent_events]
        
        unusual_patterns = [
            ["login", "login", "login", "login", "login"],
            ["download", "delete", "modify", "delete"],
        ]
        
        for pattern in unusual_patterns:
            if self._matches_pattern(event_types, pattern):
                return Anomaly(
                    id=hashlib.md5(f"{entity_id}{datetime.now()}".encode()).hexdigest()[:12],
                    timestamp=datetime.now(),
                    anomaly_type=AnomalyType.BEHAVIORAL,
                    description=f"Unusual behavior pattern detected for {entity_id}",
                    severity=0.8,
                    context={"entity_id": entity_id, "events": recent_events}
                )
        
        return None
    
    def _matches_pattern(self, events: List[str], pattern: List[str]) -> bool:
        if len(events) < len(pattern):
            return False
        
        for i in range(len(events) - len(pattern) + 1):
            if events[i:i+len(pattern)] == pattern:
                return True
        return False


class PredictiveMaintenance:
    def __init__(self):
        self.equipment: Dict[str, Dict] = {}
        self.maintenance_history: List[Dict] = []
        self.sensor_readings: Dict[str, List[Dict]] = defaultdict(list)
        
    def register_equipment(self, equipment_id: str, name: str, equipment_type: str, 
                          expected_lifetime_hours: float = 87600):
        self.equipment[equipment_id] = {
            "name": name,
            "type": equipment_type,
            "expected_lifetime_hours": expected_lifetime_hours,
            "operating_hours": 0.0,
            "health_score": 100.0,
            "last_maintenance": None,
            "next_maintenance": None,
            "condition": "good"
        }
    
    def record_sensor_reading(self, equipment_id: str, sensor_type: str, value: float):
        if equipment_id not in self.equipment:
            return
        
        self.sensor_readings[equipment_id].append({
            "sensor_type": sensor_type,
            "value": value,
            "timestamp": datetime.now()
        })
        
        if len(self.sensor_readings[equipment_id]) > 1000:
            self.sensor_readings[equipment_id] = self.sensor_readings[equipment_id][-1000:]
        
        self._update_health_score(equipment_id)
    
    def _update_health_score(self, equipment_id: str):
        equipment = self.equipment[equipment_id]
        readings = self.sensor_readings[equipment_id]
        
        if not readings:
            return
        
        temperature_readings = [r["value"] for r in readings if r["sensor_type"] == "temperature"]
        vibration_readings = [r["value"] for r in readings if r["sensor_type"] == "vibration"]
        
        health_score = 100.0
        
        if temperature_readings:
            avg_temp = sum(temperature_readings) / len(temperature_readings)
            if avg_temp > 80:
                health_score -= 20
            elif avg_temp > 60:
                health_score -= 10
        
        if vibration_readings:
            avg_vibration = sum(vibration_readings) / len(vibration_readings)
            if avg_vibration > 10:
                health_score -= 25
            elif avg_vibration > 5:
                health_score -= 10
        
        equipment["health_score"] = max(0, health_score)
        
        if health_score < 30:
            equipment["condition"] = "critical"
        elif health_score < 60:
            equipment["condition"] = "warning"
        else:
            equipment["condition"] = "good"
    
    def predict_failure(self, equipment_id: str) -> Dict:
        if equipment_id not in self.equipment:
            return {"error": "Equipment not found"}
        
        equipment = self.equipment[equipment_id]
        
        health_score = equipment["health_score"]
        operating_hours = equipment["operating_hours"]
        expected_lifetime = equipment["expected_lifetime_hours"]
        
        lifetime_ratio = operating_hours / expected_lifetime if expected_lifetime > 0 else 0
        
        if health_score < 30:
            probability = 0.9
            time_to_failure = timedelta(hours=24)
        elif health_score < 60:
            probability = 0.6
            time_to_failure = timedelta(hours=168)
        elif lifetime_ratio > 0.8:
            probability = 0.5
            time_to_failure = timedelta(hours=expected_lifetime * 0.2)
        else:
            probability = 0.1
            time_to_failure = timedelta(hours=expected_lifetime * (1 - lifetime_ratio))
        
        return {
            "equipment_id": equipment_id,
            "health_score": health_score,
            "probability_of_failure": probability,
            "estimated_time_to_failure": str(time_to_failure),
            "recommendation": "Replace soon" if probability > 0.6 else "Continue monitoring"
        }
    
    def schedule_maintenance(self, equipment_id: str, days_ahead: int = 30):
        if equipment_id not in self.equipment:
            return False
        
        scheduled_date = datetime.now() + timedelta(days=days_ahead)
        
        self.equipment[equipment_id]["next_maintenance"] = scheduled_date.isoformat()
        
        return True


class TrendAnalyzer:
    def __init__(self):
        self.time_series: Dict[str, List[Dict]] = defaultdict(list)
        
    def add_data_point(self, metric: str, value: float, timestamp: datetime = None):
        if timestamp is None:
            timestamp = datetime.now()
        
        self.time_series[metric].append({
            "value": value,
            "timestamp": timestamp
        })
    
    def detect_trend(self, metric: str, window: int = 10) -> Dict:
        if metric not in self.time_series:
            return {"trend": "unknown", "direction": "unknown"}
        
        data = self.time_series[metric]
        
        if len(data) < window:
            return {"trend": "insufficient_data", "data_points": len(data)}
        
        recent = [d["value"] for d in data[-window:]]
        
        slope = self._calculate_slope(recent)
        
        if abs(slope) < 0.1:
            direction = "stable"
        elif slope > 0:
            direction = "increasing"
        else:
            direction = "decreasing"
        
        if abs(slope) > 0.5:
            trend = "strong"
        elif abs(slope) > 0.2:
            trend = "moderate"
        else:
            trend = "weak"
        
        return {
            "trend": trend,
            "direction": direction,
            "slope": slope,
            "recent_values": recent[-5:],
            "mean": statistics.mean(recent)
        }
    
    def _calculate_slope(self, values: List[float]) -> float:
        n = len(values)
        if n < 2:
            return 0.0
        
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def forecast(self, metric: str, periods: int = 5) -> List[Forecast]:
        if metric not in self.time_series:
            return []
        
        trend_data = self.detect_trend(metric, window=20)
        
        if trend_data.get("trend") == "insufficient_data":
            return []
        
        data = self.time_series[metric][-20:]
        values = [d["value"] for d in data]
        
        mean_value = statistics.mean(values)
        slope = trend_data.get("slope", 0)
        
        forecasts = []
        
        for i in range(1, periods + 1):
            predicted = mean_value + (slope * i)
            
            confidence = 0.9 - (i * 0.1)
            confidence = max(0.5, confidence)
            
            forecast = Forecast(
                id=hashlib.md5(f"{metric}{i}{datetime.now()}".encode()).hexdigest()[:12],
                target_metric=metric,
                predicted_value=predicted,
                confidence=confidence,
                time_horizon=timedelta(days=i),
                model_type="linear_regression",
                factors=["recent_trend", "historical_mean"]
            )
            forecasts.append(forecast)
        
        return forecasts


class EarlyWarningSystem:
    def __init__(self):
        self.warning_conditions: List[Dict] = []
        self.active_warnings: List[Dict] = []
        
    def add_warning_condition(self, name: str, metric: str, threshold: float, 
                              comparison: str = "greater_than", severity: str = "warning"):
        condition = {
            "id": hashlib.md5(name.encode()).hexdigest()[:8],
            "name": name,
            "metric": metric,
            "threshold": threshold,
            "comparison": comparison,
            "severity": severity,
            "enabled": True
        }
        self.warning_conditions.append(condition)
        return condition["id"]
    
    def check_conditions(self, metrics: Dict[str, float]) -> List[Dict]:
        triggered = []
        
        for condition in self.warning_conditions:
            if not condition.get("enabled", True):
                continue
            
            metric = condition["metric"]
            if metric not in metrics:
                continue
            
            value = metrics[metric]
            threshold = condition["threshold"]
            comparison = condition["comparison"]
            
            is_triggered = False
            
            if comparison == "greater_than" and value > threshold:
                is_triggered = True
            elif comparison == "less_than" and value < threshold:
                is_triggered = True
            elif comparison == "equals" and abs(value - threshold) < 0.001:
                is_triggered = True
            elif comparison == "not_equals" and abs(value - threshold) > 0.001:
                is_triggered = True
            
            if is_triggered:
                warning = {
                    "id": hashlib.md5(f"{condition['id']}{datetime.now()}".encode()).hexdigest()[:12],
                    "condition_id": condition["id"],
                    "name": condition["name"],
                    "metric": metric,
                    "value": value,
                    "threshold": threshold,
                    "severity": condition["severity"],
                    "timestamp": datetime.now().isoformat(),
                    "message": f"{condition['name']}: {metric} is {value} ({comparison} {threshold})"
                }
                triggered.append(warning)
                self.active_warnings.append(warning)
        
        return triggered
    
    def get_active_warnings(self) -> List[Dict]:
        return self.active_warnings
    
    def dismiss_warning(self, warning_id: str) -> bool:
        for i, warning in enumerate(self.active_warnings):
            if warning["id"] == warning_id:
                self.active_warnings.pop(i)
                return True
        return False


class PredictiveAnalyticsSystem:
    def __init__(self):
        self.risk = RiskProbabilityModel()
        self.anomaly = AnomalyDetection()
        self.maintenance = PredictiveMaintenance()
        self.trends = TrendAnalyzer()
        self.early_warning = EarlyWarningSystem()
        
    def analyze_risk(self, risk_type: str, factors: Dict) -> RiskAssessment:
        return self.risk.assess_risk(risk_type, factors)
    
    def detect_anomalies(self, metric_name: str, value: float):
        self.anomaly.add_data_point(metric_name, value)
    
    def predict_equipment_failure(self, equipment_id: str) -> Dict:
        return self.maintenance.predict_failure(equipment_id)
    
    def analyze_trend(self, metric: str) -> Dict:
        return self.trends.detect_trend(metric)
    
    def forecast_metric(self, metric: str, periods: int = 5) -> List[Forecast]:
        return self.trends.forecast(metric, periods)
    
    def check_warnings(self, current_metrics: Dict[str, float]) -> List[Dict]:
        return self.early_warning.check_conditions(current_metrics)
    
    def get_threat_summary(self) -> Dict:
        return {
            "risk_summary": self.risk.get_risk_summary(),
            "active_anomalies": len(self.anomaly.get_active_anomalies()),
            "active_warnings": len(self.early_warning.get_active_warnings())
        }


_analytics_system: Optional[PredictiveAnalyticsSystem] = None

def get_analytics_system() -> PredictiveAnalyticsSystem:
    global _analytics_system
    if _analytics_system is None:
        _analytics_system = PredictiveAnalyticsSystem()
    return _analytics_system
