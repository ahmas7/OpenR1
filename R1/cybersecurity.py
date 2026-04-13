"""
R1 - Cybersecurity & Network Control Systems
Intrusion detection, encryption, firewall, malware neutralization, threat intelligence
"""
import asyncio
import logging
import hashlib
import json
import subprocess
import socket
import ssl
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
import re

logger = logging.getLogger("R1:cybersecurity")


class ThreatLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    id: str
    timestamp: datetime
    event_type: str
    source: str
    threat_level: ThreatLevel
    description: str
    raw_data: Dict = field(default_factory=dict)
    resolved: bool = False


@dataclass
class FirewallRule:
    id: str
    name: str
    action: str
    protocol: str
    source_ip: Optional[str] = None
    dest_ip: Optional[str] = None
    source_port: Optional[int] = None
    dest_port: Optional[int] = None
    enabled: bool = True
    priority: int = 100


@dataclass
class ThreatIntelligence:
    indicator: str
    indicator_type: str
    threat_type: str
    confidence: float
    source: str
    first_seen: datetime
    last_seen: datetime
    tags: List[str] = field(default_factory=list)


class IntrusionDetectionSystem:
    def __init__(self):
        self.events: List[SecurityEvent] = []
        self.attack_patterns: Dict[str, List[str]] = {}
        self.monitoring_active = False
        self._load_attack_patterns()
        
    def _load_attack_patterns(self):
        self.attack_patterns = {
            "sql_injection": [
                r"(\bUNION\b.*\bSELECT\b)",
                r"(\bOR\b.*=.*)",
                r"(--\s*$)",
            ],
            "xss": [
                r"(<script[^>]*>.*?</script>)",
                r"(javascript:)",
                r"(on\w+\s*=)",
            ],
            "path_traversal": [
                r"(\.\./)",
                r"(\.\.\\)",
                r"(/etc/passwd)",
                r"(C:\\Windows)",
            ],
            "command_injection": [
                r"(;\s*cat\s+)",
                r"(\|\s*sh\b)",
                r"(`.*`)",
                r"(\$\(.*\))",
            ],
            "brute_force": [
                r"(failed.*login)",
                r"(invalid.*password)",
                r"(authentication.*fail)",
            ],
        }
    
    def analyze_request(self, request_data: Dict) -> List[SecurityEvent]:
        events = []
        uri = request_data.get("uri", "")
        headers = request_data.get("headers", {})
        body = request_data.get("body", "")
        client_ip = request_data.get("client_ip", "unknown")
        
        combined = f"{uri} {body}"
        
        for attack_type, patterns in self.attack_patterns.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    event = SecurityEvent(
                        id=hashlib.md5(f"{attack_type}{datetime.now()}".encode()).hexdigest()[:12],
                        timestamp=datetime.now(),
                        event_type=attack_type,
                        source=client_ip,
                        threat_level=ThreatLevel.HIGH,
                        description=f"Potential {attack_type} attack detected",
                        raw_data=request_data
                    )
                    events.append(event)
                    self.events.append(event)
                    break
        
        return events
    
    def get_active_threats(self) -> List[SecurityEvent]:
        return [e for e in self.events if not e.resolved]
    
    def resolve_event(self, event_id: str) -> bool:
        for event in self.events:
            if event.id == event_id:
                event.resolved = True
                return True
        return False
    
    def get_threat_summary(self) -> Dict:
        by_level = {level: 0 for level in ThreatLevel}
        by_type = {}
        
        for event in self.events:
            by_level[event.threat_level] += 1
            by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
        
        return {
            "total_events": len(self.events),
            "active_threats": len(self.get_active_threats()),
            "by_threat_level": {k.value: v for k, v in by_level.items()},
            "by_type": by_type
        }


class EncryptionManager:
    def __init__(self):
        self.algorithms = {
            "aes-256-gcm": {"key_size": 32, "iv_size": 16},
            "aes-128-cbc": {"key_size": 16, "iv_size": 16},
            "chacha20-poly1305": {"key_size": 32, "iv_size": 12}
        }
        self.active_keys: Dict[str, bytes] = {}
        self.key_rotation_interval = 86400
        
    def generate_key(self, algorithm: str = "aes-256-gcm") -> bytes:
        if algorithm not in self.algorithms:
            raise ValueError(f"Unknown algorithm: {algorithm}")
        
        import os
        key_size = self.algorithms[algorithm]["key_size"]
        return os.urandom(key_size)
    
    def store_key(self, key_id: str, key: bytes):
        self.active_keys[key_id] = key
        
    def get_key(self, key_id: str) -> Optional[bytes]:
        return self.active_keys.get(key_id)
    
    def encrypt(self, data: bytes, key_id: str = "default", algorithm: str = "aes-256-gcm") -> bytes:
        key = self.get_key(key_id)
        if not key:
            key = self.generate_key(algorithm)
            self.store_key(key_id, key)
        
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            import os
            
            iv = os.urandom(self.algorithms[algorithm]["iv_size"])
            
            if algorithm == "aes-256-gcm" or algorithm == "aes-128-cbc":
                cipher = Cipher(
                    algorithms.AES(key),
                    modes.GCM(iv) if algorithm == "aes-256-gcm" else modes.CBC(iv),
                    backend=default_backend()
                )
            else:
                cipher = Cipher(
                    algorithms.ChaCha20Poly1305(key) if algorithm == "chacha20-poly1305" else algorithms.AES(key),
                    modes.GCM(iv),
                    backend=default_backend()
                )
            
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(data) + encryptor.finalize()
            
            if algorithm == "aes-256-gcm":
                return iv + encryptor.tag + ciphertext
            else:
                return iv + ciphertext
                
        except ImportError:
            logger.warning("cryptography library not available")
            return data
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt(self, encrypted_data: bytes, key_id: str = "default", algorithm: str = "aes-256-gcm") -> bytes:
        key = self.get_key(key_id)
        if not key:
            raise ValueError(f"Key {key_id} not found")
        
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            
            iv_size = self.algorithms[algorithm]["iv_size"]
            iv = encrypted_data[:iv_size]
            tag = encrypted_data[iv_size:iv_size+16] if algorithm == "aes-256-gcm" else b""
            ciphertext = encrypted_data[iv_size+16:] if algorithm == "aes-256-gcm" else encrypted_data[iv_size:]
            
            if algorithm == "aes-256-gcm":
                cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
            else:
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            
            decryptor = cipher.decryptor()
            return decryptor.update(ciphertext) + decryptor.finalize()
            
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise


class FirewallManager:
    def __init__(self):
        self.rules: List[FirewallRule] = []
        self.default_action = "allow"
        self.log_enabled = True
        self._load_default_rules()
        
    def _load_default_rules(self):
        self.rules = [
            FirewallRule(
                id="default-deny",
                name="Default Deny",
                action="deny",
                protocol="all",
                enabled=True,
                priority=1000
            ),
            FirewallRule(
                id="allow-http",
                name="Allow HTTP",
                action="allow",
                protocol="tcp",
                dest_port=80,
                enabled=True,
                priority=100
            ),
            FirewallRule(
                id="allow-https",
                name="Allow HTTPS", 
                action="allow",
                protocol="tcp",
                dest_port=443,
                enabled=True,
                priority=100
            ),
        ]
    
    def add_rule(self, rule: FirewallRule) -> str:
        self.rules.append(rule)
        return rule.id
    
    def remove_rule(self, rule_id: str) -> bool:
        for i, rule in enumerate(self.rules):
            if rule.id == rule_id:
                self.rules.pop(i)
                return True
        return False
    
    def check_packet(self, packet: Dict) -> bool:
        sorted_rules = sorted(self.rules, key=lambda r: r.priority)
        
        for rule in sorted_rules:
            if not rule.enabled:
                continue
            
            if self._matches_rule(packet, rule):
                return rule.action == "allow"
        
        return self.default_action == "allow"
    
    def _matches_rule(self, packet: Dict, rule: FirewallRule) -> bool:
        if rule.protocol != "all" and packet.get("protocol", "").lower() != rule.protocol.lower():
            return False
        
        if rule.source_ip and packet.get("source_ip") != rule.source_ip:
            return False
        
        if rule.dest_ip and packet.get("dest_ip") != rule.dest_ip:
            return False
        
        if rule.source_port and packet.get("source_port") != rule.source_port:
            return False
        
        if rule.dest_port and packet.get("dest_port") != rule.dest_port:
            return False
        
        return True
    
    def get_rules(self) -> List[Dict]:
        return [
            {
                "id": r.id,
                "name": r.name,
                "action": r.action,
                "protocol": r.protocol,
                "enabled": r.enabled,
                "priority": r.priority
            }
            for r in self.rules
        ]


class MalwareDetector:
    def __init__(self):
        self.signatures: Dict[str, str] = {}
        self.heuristics: List[Dict] = []
        self.quarantined: List[Dict] = []
        self._load_signatures()
        
    def _load_signatures(self):
        self.signatures = {
            "eicar": "44d88612fea8a8f36de82e1278abb02f",
            "test_malware": "098f6bcd4621d373cade4e832627b4f6",
        }
        
        self.heuristics = [
            {
                "name": "suspicious_extension",
                "patterns": [r"\.exe$", r"\.scr$", r"\.bat$", r"\.cmd$", r"\.vbs$"],
                "weight": 0.3
            },
            {
                "name": "suspicious_name",
                "patterns": [r"password", r"login", r"hack", r"crack"],
                "weight": 0.2
            },
        ]
    
    def scan_file(self, file_path: str) -> Dict:
        result = {
            "file": file_path,
            "threats": [],
            "score": 0.0,
            "action": "clean"
        }
        
        try:
            with open(file_path, "rb") as f:
                content = f.read()
                file_hash = hashlib.md5(content).hexdigest()
                
                if file_hash in self.signatures:
                    result["threats"].append({
                        "type": "known_malware",
                        "signature": file_hash,
                        "name": list(self.signatures.keys())[list(self.signatures.values()).index(file_hash)]
                    })
                    result["score"] = 1.0
                    result["action"] = "quarantine"
        
            for heuristic in self.heuristics:
                for pattern in heuristic["patterns"]:
                    if re.search(pattern, file_path, re.IGNORECASE):
                        result["threats"].append({
                            "type": "heuristic",
                            "rule": heuristic["name"]
                        })
                        result["score"] += heuristic["weight"]
            
            if result["score"] >= 0.7:
                result["action"] = "quarantine"
            elif result["score"] >= 0.3:
                result["action"] = "warn"
                
        except Exception as e:
            logger.error(f"File scan error: {e}")
            result["error"] = str(e)
        
        return result
    
    def scan_directory(self, directory: str, recursive: bool = True) -> List[Dict]:
        results = []
        
        import os
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                result = self.scan_file(file_path)
                if result["threats"]:
                    results.append(result)
            
            if not recursive:
                break
        
        return results
    
    def quarantine_file(self, file_path: str) -> bool:
        try:
            import shutil
            quarantine_path = file_path + ".quarantined"
            shutil.move(file_path, quarantine_path)
            
            self.quarantined.append({
                "original_path": file_path,
                "quarantine_path": quarantine_path,
                "timestamp": datetime.now().isoformat()
            })
            return True
        except Exception as e:
            logger.error(f"Quarantine error: {e}")
            return False


class SecureDataRouter:
    def __init__(self):
        self.routes: Dict[str, Dict] = {}
        self.active_connections: Dict[str, Dict] = {}
        
    def add_route(self, route_id: str, destination: str, encryption: bool = True, 
                  priority: int = 100):
        self.routes[route_id] = {
            "destination": destination,
            "encryption": encryption,
            "priority": priority,
            "status": "active",
            "created_at": datetime.now().isoformat()
        }
    
    def remove_route(self, route_id: str) -> bool:
        if route_id in self.routes:
            del self.routes[route_id]
            return True
        return False
    
    async def send_data(self, route_id: str, data: bytes) -> bool:
        if route_id not in self.routes:
            logger.error(f"Route {route_id} not found")
            return False
        
        route = self.routes[route_id]
        
        if route["encryption"]:
            enc_manager = EncryptionManager()
            data = enc_manager.encrypt(data)
        
        logger.info(f"Routing data via {route_id} to {route['destination']}")
        return True
    
    def get_best_route(self, destination: str) -> Optional[str]:
        matching_routes = [
            (rid, r) for rid, r in self.routes.items() 
            if r["destination"] == destination and r["status"] == "active"
        ]
        
        if not matching_routes:
            return None
        
        return min(matching_routes, key=lambda x: x[1]["priority"])[0]


class IdentityVerifier:
    def __init__(self):
        self.users: Dict[str, Dict] = {}
        self.sessions: Dict[str, Dict] = {}
        self.failed_attempts: Dict[str, List[datetime]] = {}
        self.max_attempts = 5
        self.lockout_duration = 300
        
    def register_user(self, user_id: str, credentials: Dict):
        self.users[user_id] = {
            "credentials": credentials,
            "registered_at": datetime.now().isoformat(),
            "last_login": None,
            "mfa_enabled": False
        }
    
    def verify_credentials(self, user_id: str, password: str) -> Dict:
        if self._is_locked_out(user_id):
            return {
                "success": False,
                "reason": "Account locked out",
                "lockout_until": self._get_lockout_until(user_id)
            }
        
        if user_id not in self.users:
            self._record_failed_attempt(user_id)
            return {
                "success": False,
                "reason": "Invalid credentials"
            }
        
        stored_password = self.users[user_id]["credentials"].get("password")
        
        if password == stored_password:
            self.users[user_id]["last_login"] = datetime.now().isoformat()
            self._clear_failed_attempts(user_id)
            
            session_id = self._create_session(user_id)
            
            return {
                "success": True,
                "session_id": session_id
            }
        else:
            self._record_failed_attempt(user_id)
            return {
                "success": False,
                "reason": "Invalid credentials",
                "attempts_remaining": self.max_attempts - len(self.failed_attempts.get(user_id, []))
            }
    
    def verify_session(self, session_id: str) -> bool:
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        
        if session.get("expires_at"):
            expires = datetime.fromisoformat(session["expires_at"])
            if datetime.now() > expires:
                del self.sessions[session_id]
                return False
        
        return True
    
    def _create_session(self, user_id: str) -> str:
        import uuid
        session_id = str(uuid.uuid4())
        
        self.sessions[session_id] = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
        }
        
        return session_id
    
    def _is_locked_out(self, user_id: str) -> bool:
        if user_id not in self.failed_attempts:
            return False
        
        attempts = self.failed_attempts[user_id]
        recent_attempts = [
            a for a in attempts 
            if datetime.now() - a < timedelta(seconds=self.lockout_duration)
        ]
        
        return len(recent_attempts) >= self.max_attempts
    
    def _get_lockout_until(self, user_id: str) -> str:
        if user_id not in self.failed_attempts:
            return ""
        
        attempts = self.failed_attempts[user_id]
        if attempts:
            lockout_time = attempts[-1] + timedelta(seconds=self.lockout_duration)
            return lockout_time.isoformat()
        
        return ""
    
    def _record_failed_attempt(self, user_id: str):
        self.failed_attempts.setdefault(user_id, []).append(datetime.now())
    
    def _clear_failed_attempts(self, user_id: str):
        if user_id in self.failed_attempts:
            del self.failed_attempts[user_id]


class ThreatIntelligenceGatherer:
    def __init__(self):
        self.threats: Dict[str, ThreatIntelligence] = {}
        self.feeds: List[Dict] = []
        
    def add_feed(self, feed_name: str, feed_url: str, feed_type: str = "csv"):
        self.feeds.append({
            "name": feed_name,
            "url": feed_url,
            "type": feed_type,
            "last_fetch": None
        })
    
    async def fetch_threats(self) -> int:
        count = 0
        
        for feed in self.feeds:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(feed["url"], timeout=10.0)
                    
                    if response.status_code == 200:
                        feed["last_fetch"] = datetime.now().isoformat()
                        
                        indicators = self._parse_feed(response.text, feed["type"])
                        
                        for ind in indicators:
                            threat = ThreatIntelligence(
                                indicator=ind.get("indicator", ""),
                                indicator_type=ind.get("type", "unknown"),
                                threat_type=ind.get("threat", "unknown"),
                                confidence=ind.get("confidence", 0.5),
                                source=feed["name"],
                                first_seen=datetime.now(),
                                last_seen=datetime.now()
                            )
                            self.threats[threat.indicator] = threat
                            count += 1
                            
            except Exception as e:
                logger.error(f"Feed fetch error from {feed['name']}: {e}")
        
        return count
    
    def _parse_feed(self, content: str, feed_type: str) -> List[Dict]:
        indicators = []
        
        if feed_type == "csv":
            import csv
            import io
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                indicators.append(row)
        
        return indicators
    
    def check_indicator(self, indicator: str) -> Optional[ThreatIntelligence]:
        return self.threats.get(indicator)
    
    def get_threats_by_type(self, threat_type: str) -> List[ThreatIntelligence]:
        return [t for t in self.threats.values() if t.threat_type == threat_type]


class CybersecuritySystem:
    def __init__(self):
        self.ids = IntrusionDetectionSystem()
        self.encryption = EncryptionManager()
        self.firewall = FirewallManager()
        self.malware = MalwareDetector()
        self.router = SecureDataRouter()
        self.identity = IdentityVerifier()
        self.threat_intel = ThreatIntelligenceGatherer()
        
    async def initialize(self):
        self.threat_intel.add_feed(
            "AlienVault OTX",
            "https://otx.alienvault.com/api/v1/pulses/subscribed",
            "json"
        )
        
    def analyze_request(self, request_data: Dict) -> Dict:
        events = self.ids.analyze_request(request_data)
        
        packet_allowed = self.firewall.check_packet({
            "protocol": request_data.get("protocol", "tcp"),
            "source_ip": request_data.get("client_ip"),
            "dest_port": request_data.get("port", 80)
        })
        
        return {
            "allowed": packet_allowed,
            "security_events": [
                {
                    "id": e.id,
                    "type": e.event_type,
                    "threat_level": e.threat_level.value,
                    "description": e.description
                }
                for e in events
            ],
            "action": "block" if not packet_allowed or events else "allow"
        }
    
    def encrypt_data(self, data: bytes, key_id: str = "default") -> bytes:
        return self.encryption.encrypt(data, key_id)
    
    def decrypt_data(self, encrypted_data: bytes, key_id: str = "default") -> bytes:
        return self.encryption.decrypt(encrypted_data, key_id)
    
    def scan_for_malware(self, path: str) -> Dict:
        import os
        if os.path.isdir(path):
            return {
                "results": self.malware.scan_directory(path),
                "total_threats": sum(1 for r in self.malware.scan_directory(path) if r.get("threats"))
            }
        else:
            return self.malware.scan_file(path)
    
    def authenticate(self, user_id: str, password: str) -> Dict:
        return self.identity.verify_credentials(user_id, password)
    
    def check_session(self, session_id: str) -> bool:
        return self.identity.verify_session(session_id)


_cybersecurity_system: Optional[CybersecuritySystem] = None

def get_cybersecurity_system() -> CybersecuritySystem:
    global _cybersecurity_system
    if _cybersecurity_system is None:
        _cybersecurity_system = CybersecuritySystem()
    return _cybersecurity_system
