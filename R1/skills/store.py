"""
R1 v1 - Skill Store
Persistent storage for skill state across restarts.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("R1")


class SkillStore:
    """
    Persistent storage for skill registry state.
    Uses JSON file to store loaded skills, their status, and discovery paths.
    """

    def __init__(self, db_path: str = ""):
        from ..config.settings import settings
        self.db_path = Path(db_path or Path.home() / ".r1" / "skills.json")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> Dict:
        """Load skills data from disk."""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                logger.info(f"Loaded {len(data.get('skills', []))} skills from {self.db_path}")
                return data
            except Exception as e:
                logger.warning(f"Failed to load skills store: {e}")
        return {"skills": [], "discovery_paths": [], "version": 1}

    def _save(self):
        """Save skills data to disk."""
        try:
            self._data['updated_at'] = datetime.now().isoformat()
            with open(self.db_path, 'w') as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save skills store: {e}")

    def save_skill(self, name: str, path: str, status: str, source: str = "workspace",
                   manifest: Dict = None, loaded_at: str = None):
        """
        Save or update a skill in the store.

        Args:
            name: Skill name
            path: Path to skill directory
            status: Skill status (loaded, unloaded, error)
            source: Skill source (bundled, workspace, local)
            manifest: Skill manifest dict
            loaded_at: ISO timestamp when loaded
        """
        # Find existing skill
        existing = None
        for skill in self._data['skills']:
            if skill['name'] == name:
                existing = skill
                break

        skill_data = {
            'name': name,
            'path': str(path),
            'status': status,
            'source': source,
            'manifest': manifest or {},
            'saved_at': datetime.now().isoformat()
        }

        if loaded_at:
            skill_data['loaded_at'] = loaded_at

        if existing:
            existing.update(skill_data)
        else:
            self._data['skills'].append(skill_data)

        self._save()
        logger.debug(f"Saved skill '{name}' to store (status: {status})")

    def remove_skill(self, name: str):
        """Remove a skill from the store."""
        self._data['skills'] = [s for s in self._data['skills'] if s['name'] != name]
        self._save()

    def get_saved_skills(self, status: str = None) -> List[Dict[str, Any]]:
        """
        Get all saved skills, optionally filtered by status.

        Args:
            status: Filter by status (loaded, unloaded, error) or None for all

        Returns:
            List of skill data dicts
        """
        skills = self._data.get('skills', [])
        if status:
            skills = [s for s in skills if s.get('status') == status]
        return skills

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific skill by name."""
        for skill in self._data.get('skills', []):
            if skill['name'] == name:
                return skill
        return None

    def add_discovery_path(self, path: str):
        """Add a discovery path."""
        path_str = str(path)
        if path_str not in self._data.get('discovery_paths', []):
            self._data.setdefault('discovery_paths', []).append(path_str)
            self._save()

    def get_discovery_paths(self) -> List[str]:
        """Get all saved discovery paths."""
        return self._data.get('discovery_paths', [])

    def clear(self):
        """Clear all saved skills."""
        self._data['skills'] = []
        self._save()
        logger.info("Cleared skills store")

    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        skills = self._data.get('skills', [])
        return {
            'total_skills': len(skills),
            'loaded': len([s for s in skills if s.get('status') == 'loaded']),
            'unloaded': len([s for s in skills if s.get('status') == 'unloaded']),
            'errors': len([s for s in skills if s.get('status') == 'error']),
            'db_path': str(self.db_path)
        }
