"""
R1 CLI
Command-line interface for R1 core runtime.
"""
import click
import httpx
from rich.console import Console
from rich.table import Table

console = Console()

API_BASE = "http://localhost:8000"
HTTP_TIMEOUT = httpx.Timeout(20.0)


@click.group()
@click.version_option(version="2.0.0")
def cli():
    """R1 - Personal AI Assistant CLI"""
    pass


@cli.command()
@click.argument("message")
@click.option("--session", "session_id", default="default", help="Session id")
def chat(message, session_id):
    """Chat with R1"""
    try:
        response = httpx.post(
            f"{API_BASE}/chat",
            json={"message": message, "session_id": session_id},
            timeout=HTTP_TIMEOUT,
        )
        data = response.json()
        console.print(f"R1: {data.get('response', '')}")
    except Exception as e:
        console.print(f"Error: {e}")


@cli.command()
def status():
    """Check core runtime status"""
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            health = client.get(f"{API_BASE}/health").json()
            providers = client.get(f"{API_BASE}/providers").json()
            tools = client.get(f"{API_BASE}/tools").json()
            skills = client.get(f"{API_BASE}/skills").json()
            sessions = client.get(f"{API_BASE}/sessions").json()

        console.print("R1 Status")
        console.print(f"Status: {health.get('status')}")
        console.print(f"Active provider: {providers.get('active_provider')}")
        console.print(f"Tools: {len(tools.get('tools', []))}")
        console.print(f"Skills: {len(skills.get('skills', []))}")
        console.print(f"Sessions: {len(sessions.get('sessions', []))}")

        provider_table = Table(title="Providers")
        provider_table.add_column("ID", style="cyan")
        provider_table.add_column("Healthy", style="green")
        provider_table.add_column("Reason", style="yellow")
        for p in providers.get("providers", []):
            provider_table.add_row(
                p.get("id", ""),
                "yes" if p.get("healthy") else "no",
                p.get("reason", "") or "",
            )
        console.print(provider_table)
    except Exception as e:
        console.print(f"Error: {e}")


@cli.group()
def agent():
    """Agent commands"""
    pass


@agent.command("run")
@click.argument("goal")
@click.option("--session", "session_id", default="default", help="Session id")
def agent_run(goal, session_id):
    """Run agent with a goal"""
    try:
        response = httpx.post(
            f"{API_BASE}/agent/run",
            json={"goal": goal, "session_id": session_id},
            timeout=HTTP_TIMEOUT,
        )
        console.print(response.json())
    except Exception as e:
        console.print(f"Error: {e}")


@agent.command("status")
@click.argument("session_id")
def agent_status(session_id):
    """Get agent session status"""
    try:
        response = httpx.get(f"{API_BASE}/agent/status/{session_id}", timeout=HTTP_TIMEOUT)
        console.print(response.json())
    except Exception as e:
        console.print(f"Error: {e}")


@agent.command("stop")
@click.argument("session_id")
def agent_stop(session_id):
    """Stop an agent session"""
    try:
        response = httpx.post(f"{API_BASE}/agent/stop/{session_id}", timeout=HTTP_TIMEOUT)
        console.print(response.json())
    except Exception as e:
        console.print(f"Error: {e}")


@cli.command("sessions")
def list_sessions():
    """List sessions"""
    try:
        response = httpx.get(f"{API_BASE}/sessions", timeout=HTTP_TIMEOUT)
        data = response.json()

        table = Table(title="Sessions")
        table.add_column("Session", style="cyan")
        table.add_column("Status", style="green")
        for s in data.get("sessions", []):
            table.add_row(s.get("session_id", ""), s.get("status", ""))
        console.print(table)
    except Exception as e:
        console.print(f"Error: {e}")


@cli.command("tools")
def list_tools():
    """List tools"""
    try:
        response = httpx.get(f"{API_BASE}/tools", timeout=HTTP_TIMEOUT)
        data = response.json()
        for tool in data.get("tools", []):
            console.print(tool)
    except Exception as e:
        console.print(f"Error: {e}")


@cli.command("skills")
def list_skills():
    """List skills"""
    try:
        response = httpx.get(f"{API_BASE}/skills", timeout=HTTP_TIMEOUT)
        data = response.json()
        for skill in data.get("skills", []):
            console.print(skill)
    except Exception as e:
        console.print(f"Error: {e}")


@cli.command("memory")
@click.argument("session_id")
def show_memory(session_id):
    """Show session memory"""
    try:
        response = httpx.get(f"{API_BASE}/memory/{session_id}", timeout=HTTP_TIMEOUT)
        console.print(response.json())
    except Exception as e:
        console.print(f"Error: {e}")


if __name__ == "__main__":
    cli()
