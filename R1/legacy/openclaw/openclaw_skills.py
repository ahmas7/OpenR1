"""
OpenClaw-Style Skills for R1
Pre-built skills for common personal assistant tasks
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from R1.tools import get_tool_registry

try:
    from R1.legacy.openclaw.openclaw_persona import persona
except ImportError:
    persona = None
try:
    from R1.legacy.openclaw.openclaw_proactive import add_reminder
except ImportError:

    def add_reminder(task, due):
        pass


logger = logging.getLogger("R1:openclaw_skills")


class GmailSkill:
    """
    Gmail integration skill
    Read emails, send emails, manage inbox
    """

    def __init__(self):
        self.credentials_path = os.getenv("GMAIL_CREDENTIALS_PATH")
        self.token_path = Path.home() / ".r1" / "gmail_token.json"

    def is_configured(self) -> bool:
        """Check if Gmail is configured"""
        return bool(os.getenv("GMAIL_USER")) and bool(os.getenv("GMAIL_APP_PASSWORD"))

    async def send_email(self, to: str, subject: str, body: str) -> str:
        """Send an email"""
        if not self.is_configured():
            return "Gmail not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD in .env"

        try:
            tool_registry = get_tool_registry()
            result = await tool_registry.execute(
                "email.send_email", {"to": to, "subject": subject, "body": body}
            )
            if result.get("success"):
                return f"✉️ Email sent to {to}"
            else:
                return f"❌ Failed to send email: {result.get('error')}"
        except Exception as e:
            return f"❌ Error: {str(e)}"

    async def check_inbox(self, limit: int = 5) -> str:
        """Check email inbox"""
        if not self.is_configured():
            return "Gmail not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD in .env"

        try:
            tool_registry = get_tool_registry()
            result = await tool_registry.execute("email.check_inbox", {"limit": limit})
            if result.get("success"):
                emails = result.get("emails", [])
                if emails:
                    lines = [f"📧 {len(emails)} email(s) in inbox:"]
                    for i, email in enumerate(emails[:limit], 1):
                        lines.append(
                            f"{i}. {email.get('preview', 'No preview')[:80]}..."
                        )
                    return "\n".join(lines)
                else:
                    return "📭 No new emails."
            else:
                return f"❌ Failed to check inbox: {result.get('error')}"
        except Exception as e:
            return f"❌ Error: {str(e)}"


class CalendarSkill:
    """
    Calendar management skill
    Add events, view schedule, check availability
    """

    async def add_event(
        self, title: str, date_str: str, time_str: str = "", description: str = ""
    ) -> str:
        """Add an event to calendar"""
        try:
            # Parse date if natural language
            parsed_date = self._parse_date(date_str)

            tool_registry = get_tool_registry()
            result = await tool_registry.execute(
                "calendar.add_event",
                {
                    "title": title,
                    "date": parsed_date,
                    "time": time_str,
                    "description": description,
                },
            )

            if result.get("success"):
                event = result.get("event", {})
                return f"📅 Added: {event.get('title')} on {event.get('date')}"
            else:
                return f"❌ Failed to add event: {result.get('error')}"
        except Exception as e:
            return f"❌ Error: {str(e)}"

    async def get_events(self, date_str: str = None) -> str:
        """Get events for a date"""
        try:
            parsed_date = self._parse_date(date_str) if date_str else None

            tool_registry = get_tool_registry()
            result = await tool_registry.execute(
                "calendar.get_events", {"date": parsed_date}
            )

            if result.get("success"):
                events = result.get("events", [])
                if events:
                    date_label = parsed_date or "upcoming"
                    lines = [f"📅 Events for {date_label}:"]
                    for e in events:
                        time_str = f" at {e.get('time')}" if e.get("time") else ""
                        lines.append(f"  • {e.get('title')}{time_str}")
                    return "\n".join(lines)
                else:
                    return "📭 No events found."
            else:
                return f"❌ Failed to get events: {result.get('error')}"
        except Exception as e:
            return f"❌ Error: {str(e)}"

    def _parse_date(self, date_str: str) -> str:
        """Parse natural language date"""
        date_str = date_str.lower().strip()
        today = datetime.now()

        if date_str in ["today"]:
            return today.strftime("%Y-%m-%d")
        elif date_str in ["tomorrow"]:
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")
        elif date_str in ["next week"]:
            return (today + timedelta(weeks=1)).strftime("%Y-%m-%d")
        elif date_str in ["next monday", "monday"]:
            days_ahead = 0 - today.weekday() + 7  # Next Monday
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        # Return as-is if already formatted
        return date_str


class TodoSkill:
    """
    Todo list management skill
    Add tasks, complete tasks, view list
    """

    def __init__(self):
        self.todo_file = Path("E:/MYAI/R1/data/todos.json")
        self.todos: List[Dict] = []
        self._load()

    def _load(self):
        """Load todos from file"""
        if self.todo_file.exists():
            try:
                self.todos = json.loads(self.todo_file.read_text())
            except Exception:
                self.todos = []

    def _save(self):
        """Save todos to file"""
        self.todo_file.parent.mkdir(parents=True, exist_ok=True)
        self.todo_file.write_text(json.dumps(self.todos, indent=2))

    def add_todo(self, task: str, priority: str = "normal", due: str = None) -> str:
        """Add a todo item"""
        todo = {
            "id": len(self.todos) + 1,
            "task": task,
            "priority": priority,
            "due": due,
            "completed": False,
            "created_at": datetime.now().isoformat(),
        }
        self.todos.append(todo)
        self._save()

        # Also add as reminder if due date
        if due:
            add_reminder(task, due)

        return f"✅ Added to list: {task}"

    def complete_todo(self, task_id: int) -> str:
        """Mark a todo as complete"""
        for todo in self.todos:
            if todo["id"] == task_id:
                todo["completed"] = True
                todo["completed_at"] = datetime.now().isoformat()
                self._save()
                return f"✓ Completed: {todo['task']}"
        return f"❌ Task #{task_id} not found"

    def list_todos(self, show_completed: bool = False) -> str:
        """List todos"""
        if not self.todos:
            return "📝 No todos yet."

        lines = ["Your todo list:"]
        pending = [t for t in self.todos if not t.get("completed")]
        completed = [t for t in self.todos if t.get("completed")]

        if pending:
            lines.append(f"\n⏳ Pending ({len(pending)}):")
            for t in pending:
                priority_emoji = {
                    "urgent": "🔴",
                    "high": "🟠",
                    "normal": "⚪",
                    "low": "⚪",
                }.get(t.get("priority", "normal"), "⚪")
                lines.append(f"  {priority_emoji} #{t['id']}: {t['task']}")

        if show_completed and completed:
            lines.append(f"\n✅ Completed ({len(completed)}):")
            for t in completed[-5:]:  # Show last 5 completed
                lines.append(f"  ✓ {t['task']}")

        return "\n".join(lines)


class WebSearchSkill:
    """
    Web search skill
    Search the internet for information
    """

    async def search(self, query: str, num_results: int = 3) -> str:
        """Search the web"""
        try:
            import httpx
            from bs4 import BeautifulSoup

            # Use DuckDuckGo HTML search (no API key needed)
            url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                soup = BeautifulSoup(response.text, "html.parser")

                results = []
                for result in soup.select(".result")[:num_results]:
                    title_elem = result.select_one(".result__title")
                    snippet_elem = result.select_one(".result__snippet")

                    if title_elem and snippet_elem:
                        results.append(
                            {
                                "title": title_elem.get_text(strip=True),
                                "snippet": snippet_elem.get_text(strip=True)[:150],
                            }
                        )

                if results:
                    lines = [f"🔍 Search results for '{query}':"]
                    for i, r in enumerate(results, 1):
                        lines.append(f"\n{i}. {r['title']}")
                        lines.append(f"   {r['snippet']}...")
                    return "\n".join(lines)
                else:
                    return f"🔍 No results found for '{query}'."

        except Exception as e:
            return f"❌ Search error: {str(e)}"


class WeatherSkill:
    """
    Weather skill
    Get current weather and forecasts
    """

    def __init__(self):
        self.api_key = os.getenv("OPENWEATHER_API_KEY")
        self.default_city = os.getenv("DEFAULT_CITY", "New York")

    def is_configured(self) -> bool:
        """Check if weather is configured"""
        return bool(self.api_key)

    async def get_weather(self, city: str = None) -> str:
        """Get weather for a city"""
        if not self.is_configured():
            return "Weather not configured. Set OPENWEATHER_API_KEY in .env"

        city = city or self.default_city

        try:
            import httpx

            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.api_key}&units=metric"

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                data = response.json()

                if response.status_code == 200:
                    temp = data["main"]["temp"]
                    feels_like = data["main"]["feels_like"]
                    description = data["weather"][0]["description"]
                    humidity = data["main"]["humidity"]

                    return f"🌤️ Weather in {city}: {description}, {temp:.1f}°C (feels like {feels_like:.1f}°C), {humidity}% humidity"
                else:
                    return f"❌ Could not get weather: {data.get('message', 'Unknown error')}"

        except Exception as e:
            return f"❌ Weather error: {str(e)}"


class SpotifySkill:
    """
    Spotify control skill
    Play, pause, skip, control volume
    """

    def __init__(self):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    def is_configured(self) -> bool:
        """Check if Spotify is configured"""
        return bool(self.client_id and self.client_secret)

    async def play(self, query: str = None) -> str:
        """Play music"""
        if not self.is_configured():
            return "Spotify not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env"

        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth

            sp = spotipy.Spotify(
                auth_manager=SpotifyOAuth(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    redirect_uri="http://localhost:8888/callback",
                    scope="user-modify-playback-state,user-read-playback-state",
                )
            )

            if query:
                results = sp.search(q=query, limit=1)
                if results["tracks"]["items"]:
                    track = results["tracks"]["items"][0]
                    sp.start_playback(uris=[track["uri"]])
                    return f"🎵 Now playing: {track['name']} by {track['artists'][0]['name']}"
                else:
                    return f"❌ Could not find '{query}'"
            else:
                sp.start_playback()
                return "🎵 Resumed playback"

        except Exception as e:
            return f"❌ Spotify error: {str(e)}"

    async def pause(self) -> str:
        """Pause music"""
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth

            sp = spotipy.Spotify(
                auth_manager=SpotifyOAuth(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    redirect_uri="http://localhost:8888/callback",
                    scope="user-modify-playback-state,user-read-playback-state",
                )
            )

            sp.pause_playback()
            return "⏸️ Paused"
        except Exception as e:
            return f"❌ Error: {str(e)}"


class FileManagerSkill:
    """
    File management skill
    Read, write, search files
    """

    async def read_file(self, path: str) -> str:
        """Read a file"""
        tool_registry = get_tool_registry()
        result = await tool_registry.execute("file.read_file", {"path": path})
        if result.get("success"):
            content = result.get("content", "")
            # Truncate if too long
            if len(content) > 2000:
                content = content[:2000] + "\n... (truncated)"
            return f"📄 {path}:\n```\n{content}\n```"
        else:
            return f"❌ {result.get('error')}"

    async def search_files(self, directory: str, query: str) -> str:
        """Search for files"""
        tool_registry = get_tool_registry()
        result = await tool_registry.execute(
            "file.search_files", {"directory": directory, "query": query}
        )
        if result.get("success"):
            results = result.get("results", [])
            if results:
                lines = [f"🔍 Found {len(results)} file(s) matching '{query}':"]
                for r in results[:10]:
                    lines.append(f"  • {r['name']}")
                return "\n".join(lines)
            else:
                return f"🔍 No files found matching '{query}'"
        else:
            return f"❌ {result.get('error')}"

    async def write_file(self, path: str, content: str) -> str:
        """Write a file"""
        tool_registry = get_tool_registry()
        result = await tool_registry.execute(
            "file.write_file", {"path": path, "content": content}
        )
        if result.get("success"):
            return f"✅ Saved to {path}"
        else:
            return f"❌ {result.get('error')}"


# === Skill Registry ===


class SkillRegistry:
    """Registry of all OpenClaw-style skills"""

    def __init__(self):
        self.gmail = GmailSkill()
        self.calendar = CalendarSkill()
        self.todo = TodoSkill()
        self.web_search = WebSearchSkill()
        self.weather = WeatherSkill()
        self.spotify = SpotifySkill()
        self.files = FileManagerSkill()

        self._register_commands()

    def _register_commands(self):
        """Register natural language command handlers"""
        self.commands = {
            # Email commands
            "send email": self.gmail.send_email,
            "email": self.gmail.send_email,
            "check email": self.gmail.check_inbox,
            "check inbox": self.gmail.check_inbox,
            # Calendar commands
            "add event": self.calendar.add_event,
            "schedule": self.calendar.add_event,
            "what's on": self.calendar.get_events,
            "calendar": self.calendar.get_events,
            # Todo commands
            "add todo": self.todo.add_todo,
            "new task": self.todo.add_todo,
            "todo list": self.todo.list_todos,
            "show todos": self.todo.list_todos,
            "complete": self.todo.complete_todo,
            "done": self.todo.complete_todo,
            # Search commands
            "search": self.web_search.search,
            "look up": self.web_search.search,
            "google": self.web_search.search,
            # Weather commands
            "weather": self.weather.get_weather,
            "temperature": self.weather.get_weather,
            # Spotify commands
            "play": self.spotify.play,
            "pause music": self.spotify.pause,
            "pause": self.spotify.pause,
            # File commands
            "read file": self.files.read_file,
            "open file": self.files.read_file,
            "search files": self.files.search_files,
            "find file": self.files.search_files,
            "write file": self.files.write_file,
            "save to": self.files.write_file,
        }

    async def process_command(self, text: str) -> Optional[str]:
        """
        Try to process text as a skill command
        Returns response if handled, None otherwise
        """
        text_lower = text.lower()

        for command, handler in self.commands.items():
            if command in text_lower:
                # Extract arguments (basic)
                # This is simplified - real implementation would use proper NLP
                return await handler(text)

        return None

    def get_available_skills(self) -> List[str]:
        """Get list of available skills"""
        skills = []
        if self.gmail.is_configured():
            skills.append("📧 Gmail")
        if self.weather.is_configured():
            skills.append("🌤️ Weather")
        if self.spotify.is_configured():
            skills.append("🎵 Spotify")
        skills.extend(["📅 Calendar", "📝 Todos", "🔍 Web Search", "📁 File Manager"])
        return skills


# Global skill registry
skill_registry = SkillRegistry()
