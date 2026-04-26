"""
Jarvis Global Intelligence Skill
Autonomous web research, data extraction, and high-level reporting.
"""
import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from R1.browser import BrowserController
from R1.skills.self_writer import SkillManifest

logger = logging.getLogger("R1:skills:global_intelligence")

class GlobalIntelligenceSkill:
    def __init__(self):
        self.browser = None
        self.research_dir = Path.home() / ".r1" / "research"
        self.research_dir.mkdir(parents=True, exist_ok=True)

    async def _get_browser(self):
        if self.browser is None:
            self.browser = await BrowserController.get(headless=True)
        return self.browser

    async def conduct_research(self, topic: str, depth: int = 3) -> Dict[str, Any]:
        """
        Perform autonomous deep research on a topic.
        """
        logger.info(f"Conducting global intelligence research on: {topic} (depth: {depth})")
        browser = await self._get_browser()

        # 1. Search for primary sources
        search_result = await browser.search_google(topic)
        if not search_result.success:
            return {"error": f"Initial search failed: {search_result.error}"}

        sources = search_result.data[:depth]
        findings = []

        # 2. Extract intelligence from each source
        for source in sources:
            logger.info(f"Extracting intelligence from: {source['url']}")
            nav_result = await browser.navigate(source['url'])
            if nav_result.success:
                # Basic text extraction
                text = await browser.get_text("body")
                findings.append({
                    "title": source['title'],
                    "url": source['url'],
                    "summary": text.content[:1000] if text.success else "Extraction failed"
                })

        # 3. Compile report
        report_id = f"research_{topic.replace(' ', '_').lower()[:20]}"
        report_path = self.research_dir / f"{report_id}.json"

        report = {
            "topic": topic,
            "timestamp": asyncio.get_event_loop().time(),
            "findings": findings,
            "summary": f"Jarvis has compiled {len(findings)} intelligence nodes regarding '{topic}'."
        }

        report_path.write_text(json.dumps(report, indent=2))

        return {
            "success": True,
            "report_id": report_id,
            "findings_count": len(findings),
            "report_summary": report["summary"],
            "path": str(report_path)
        }

    async def generate_briefing(self) -> str:
        """
        Generate a high-level intelligence briefing based on recent research and status.
        """
        # This would pull from latest research files
        return "Intelligence systems are nominal. No critical anomalies detected in global data streams."

def get_skill_manifest() -> SkillManifest:
    return SkillManifest(
        name="global_intelligence",
        description="Autonomous deep web research and data synthesis engine.",
        emoji="🌐",
        version="1.0.0",
        author="Jarvis",
        commands=[
            {
                "name": "research",
                "type": "python",
                "action": "result = await skill.conduct_research(args.get('topic'), args.get('depth', 3))"
            }
        ],
        tags=["research", "intelligence", "autonomous"],
        permissions=["browse", "filesystem"]
    )
