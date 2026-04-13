"""
R1 - Tool Ecosystem
Email, Calendar, Notifications, File System Tools
"""
import os
import asyncio
import json
import smtplib
import poplib
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


@dataclass
class EmailMessage:
    from_addr: str
    to_addr: str
    subject: str
    body: str
    date: str = ""


class EmailTool:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.pop_server = os.getenv("POP_SERVER", "")
        self.pop_user = os.getenv("POP_USER", "")
        self.pop_password = os.getenv("POP_PASSWORD", "")
    
    def is_configured(self) -> bool:
        return bool(self.smtp_server and self.smtp_user)
    
    async def send_email(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        if not self.is_configured():
            return {"success": False, "error": "Email not configured"}
        
        try:
            msg = MIMEMultipart()
            msg["From"] = self.smtp_user
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            return {"success": True, "message": f"Email sent to {to}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def check_inbox(self, limit: int = 10) -> Dict[str, Any]:
        if not self.pop_server:
            return {"success": False, "error": "POP not configured"}
        
        try:
            server = poplib.POP3(self.pop_server)
            server.user(self.pop_user)
            server.pass_(self.pop_password)
            
            num_messages = len(server.list()[1])
            emails = []
            
            for i in range(min(limit, num_messages)):
                msg_bytes = server.retr(i + 1)[1]
                msg_str = b"\n".join(msg_bytes).decode()
                emails.append({"id": i + 1, "preview": msg_str[:200]})
            
            server.quit()
            
            return {"success": True, "count": num_messages, "emails": emails}
        except Exception as e:
            return {"success": False, "error": str(e)}


class CalendarTool:
    def __init__(self):
        self.calendar_file = Path("E:/MYAI/R1/data/calendar.yaml")
        self.calendar_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.calendar_file.exists():
            self.calendar_file.write_text("events: []")
    
    async def add_event(self, title: str, date: str, time: str = "", description: str = "") -> Dict[str, Any]:
        try:
            data = yaml.safe_load(self.calendar_file.read_text()) or {"events": []}
            
            event = {
                "id": len(data["events"]) + 1,
                "title": title,
                "date": date,
                "time": time,
                "description": description,
                "created": datetime.now().isoformat()
            }
            
            data["events"].append(event)
            self.calendar_file.write_text(yaml.dump(data))
            
            return {"success": True, "event": event}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_events(self, date: str = None) -> Dict[str, Any]:
        try:
            data = yaml.safe_load(self.calendar_file.read_text()) or {"events": []}
            
            if date:
                events = [e for e in data["events"] if e["date"] == date]
            else:
                events = data["events"]
            
            return {"success": True, "events": events}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def delete_event(self, event_id: int) -> Dict[str, Any]:
        try:
            data = yaml.safe_load(self.calendar_file.read_text()) or {"events": []}
            data["events"] = [e for e in data["events"] if e["id"] != event_id]
            self.calendar_file.write_text(yaml.dump(data))
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


class NotificationTool:
    def __init__(self):
        self.enabled = True
    
    async def send(self, title: str, message: str, urgency: str = "normal") -> Dict[str, Any]:
        if not self.enabled:
            return {"success": False, "error": "Notifications disabled"}
        
        try:
            import win10toast
            win10toast.ToastNotifier().show_toast(
                title=title,
                msg=message,
                duration=5
            )
            return {"success": True}
        except ImportError:
            return {"success": False, "error": "win10toast not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class FileTool:
    async def read_file(self, path: str) -> Dict[str, Any]:
        try:
            p = Path(path)
            if not p.exists():
                return {"success": False, "error": "File not found"}
            
            content = p.read_text(encoding="utf-8")
            return {"success": True, "content": content, "size": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def write_file(self, path: str, content: str) -> Dict[str, Any]:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            
            return {"success": True, "path": str(p)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def list_files(self, directory: str, pattern: str = "*") -> Dict[str, Any]:
        try:
            p = Path(directory)
            if not p.exists():
                return {"success": False, "error": "Directory not found"}
            
            files = [{"name": f.name, "size": f.stat().st_size, "is_dir": f.is_dir()} 
                    for f in p.glob(pattern)]
            
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def search_files(self, directory: str, query: str) -> Dict[str, Any]:
        try:
            p = Path(directory)
            results = []
            
            for f in p.rglob("*"):
                if f.is_file() and query.lower() in f.name.lower():
                    results.append({"name": f.name, "path": str(f)})
            
            return {"success": True, "results": results[:50]}
        except Exception as e:
            return {"success": False, "error": str(e)}


class DatabaseTool:
    def __init__(self, db_path: str = "E:/MYAI/R1/data/orion.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def query(self, sql: str, params: tuple = ()) -> Dict[str, Any]:
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            
            if sql.strip().upper().startswith("SELECT"):
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                conn.close()
                return {"success": True, "columns": columns, "rows": rows}
            else:
                conn.commit()
                conn.close()
                return {"success": True, "affected": cursor.rowcount}
        except Exception as e:
            return {"success": False, "error": str(e)}


class Tools:
    def __init__(self):
        self.email = EmailTool()
        self.calendar = CalendarTool()
        self.notification = NotificationTool()
        self.file = FileTool()
        self.database = DatabaseTool()
    
    async def execute(self, tool_name: str, action: str, **kwargs) -> Dict[str, Any]:
        tool = getattr(self, tool_name, None)
        if not tool:
            return {"success": False, "error": f"Tool {tool_name} not found"}
        
        method = getattr(tool, action, None)
        if not method:
            return {"success": False, "error": f"Action {action} not found"}
        
        return await method(**kwargs)


tools = Tools()
