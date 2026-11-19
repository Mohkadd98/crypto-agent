"""
Skill registry for the Crypto Intelligence Agent.
Manages skill loading, activation, and lifecycle.
"""

import json
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

from core.config import get_settings
from core.tool_registry import get_tool_registry, SKILL_TOOL_MAP


class SkillStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    INSTALLED = "installed"
    ERROR = "error"
    LOADING = "loading"


@dataclass
class Skill:
    """Represents a skill."""
    name: str
    display_name: str
    description: str
    version: str
    status: SkillStatus = SkillStatus.INSTALLED
    dependencies: List[str] = field(default_factory=list)
    required_apis: List[str] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    instructions: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    is_core: bool = False
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_error: Optional[str] = None
    skill_module: Optional[Any] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "required_apis": self.required_apis,
            "available_tools": self.available_tools,
            "instructions": self.instructions,
            "config": self.config,
            "is_core": self.is_core,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_error": self.last_error
        }


class SkillRegistry:
    """Registry for managing skills."""
    
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self._skills: Dict[str, Skill] = {}
        self._load_order: List[str] = []
        self._tool_registry = get_tool_registry()
    
    def discover_skills(self) -> List[str]:
        """Discover all skill directories."""
        skill_dirs = []
        if self.skills_dir.exists():
            for item in self.skills_dir.iterdir():
                if item.is_dir() and not item.name.startswith("__"):
                    skill_md = item / "SKILL.md"
                    skill_py = item / "skill.py"
                    if skill_md.exists() or skill_py.exists():
                        skill_dirs.append(item.name)
        return skill_dirs
    
    def load_skill_manifest(self, skill_name: str) -> Optional[Dict]:
        """Load skill manifest from SKILL.md."""
        skill_path = self.skills_dir / skill_name
        skill_md = skill_path / "SKILL.md"
        
        if not skill_md.exists():
            return None
        
        content = skill_md.read_text(encoding="utf-8")
        
        # Parse markdown frontmatter and content
        manifest = {
            "name": skill_name,
            "display_name": skill_name.replace("_", " ").title(),
            "description": "",
            "version": "1.0.0",
            "dependencies": [],
            "required_apis": [],
            "available_tools": [],
            "instructions": content,
            "config": {},
            "is_core": False,
            "priority": 0
        }
        
        # Try to parse YAML frontmatter
        if content.startswith("---"):
            try:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    import yaml
                    frontmatter = yaml.safe_load(parts[1])
                    if frontmatter:
                        manifest.update(frontmatter)
                    manifest["instructions"] = parts[2].strip()
            except Exception:
                pass
        
        return manifest
    
    def load_skill_module(self, skill_name: str) -> Optional[Any]:
        """Load skill Python module."""
        skill_path = self.skills_dir / skill_name
        skill_py = skill_path / "skill.py"
        
        if not skill_py.exists():
            return None
        
        try:
            spec = importlib.util.spec_from_file_location(f"skill_{skill_name}", skill_py)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"skill_{skill_name}"] = module
                spec.loader.exec_module(module)
                return module
        except Exception as e:
            print(f"Failed to load skill module {skill_name}: {e}")
        
        return None
    
    def register_skill(self, skill: Skill) -> bool:
        """Register a skill."""
        # Check dependencies
        for dep in skill.dependencies:
            if dep not in self._skills:
                skill.status = SkillStatus.ERROR
                skill.last_error = f"Missing dependency: {dep}"
                return False
            if self._skills[dep].status != SkillStatus.ACTIVE:
                skill.status = SkillStatus.ERROR
                skill.last_error = f"Dependency not active: {dep}"
                return False
        
        self._skills[skill.name] = skill
        
        # Register tools for this skill
        if skill.available_tools:
            for tool_name in skill.available_tools:
                tool = self._tool_registry.get_tool(tool_name)
                if tool:
                    tool.skill_name = skill.name
        
        return True
    
    def activate_skill(self, name: str) -> bool:
        """Activate a skill."""
        if name not in self._skills:
            return False
        
        skill = self._skills[name]
        
        # Load module if not loaded
        if skill.skill_module is None:
            skill.skill_module = self.load_skill_module(name)
        
        # Call activation hook if exists
        if skill.skill_module and hasattr(skill.skill_module, "on_activate"):
            try:
                skill.skill_module.on_activate(skill.config)
            except Exception as e:
                skill.status = SkillStatus.ERROR
                skill.last_error = f"Activation failed: {e}"
                return False
        
        skill.status = SkillStatus.ACTIVE
        skill.updated_at = datetime.utcnow()
        return True
    
    def deactivate_skill(self, name: str) -> bool:
        """Deactivate a skill."""
        if name not in self._skills:
            return False
        
        skill = self._skills[name]
        
        # Call deactivation hook if exists
        if skill.skill_module and hasattr(skill.skill_module, "on_deactivate"):
            try:
                skill.skill_module.on_deactivate()
            except Exception as e:
                skill.last_error = f"Deactivation error: {e}"
        
        skill.status = SkillStatus.INACTIVE
        skill.updated_at = datetime.utcnow()
        return True
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)
    
    def list_skills(self, status: Optional[SkillStatus] = None) -> List[Skill]:
        """List all skills, optionally filtered by status."""
        skills = list(self._skills.values())
        if status:
            skills = [s for s in skills if s.status == status]
        return sorted(skills, key=lambda s: (-s.priority, s.name))
    
    def get_active_skills(self) -> List[Skill]:
        """Get all active skills."""
        return self.list_skills(SkillStatus.ACTIVE)
    
    def get_skill_tools(self, skill_name: str) -> List[str]:
        """Get tools available for a skill."""
        skill = self._skills.get(skill_name)
        if skill:
            return skill.available_tools
        return SKILL_TOOL_MAP.get(skill_name, [])
    
    def load_all_skills(self, auto_activate: bool = True) -> Dict[str, bool]:
        """Load all discovered skills."""
        results = {}
        discovered = self.discover_skills()
        
        # Load core skills first based on priority
        skills_config = get_settings().skills
        core_skills = skills_config.enabled_by_default
        
        # Sort by priority from config
        skill_priorities = {}
        for skill_name in discovered:
            manifest = self.load_skill_manifest(skill_name)
            if manifest:
                skill_priorities[skill_name] = manifest.get("priority", 999)
        
        # Load in priority order
        for skill_name in sorted(discovered, key=lambda s: skill_priorities.get(s, 999)):
            success = self.load_skill(skill_name)
            results[skill_name] = success
            
            if success and auto_activate and (skill_name in core_skills or self._skills[skill_name].is_core):
                self.activate_skill(skill_name)
        
        return results
    
    def load_skill(self, skill_name: str) -> bool:
        """Load a single skill."""
        if skill_name in self._skills:
            return True
        
        manifest = self.load_skill_manifest(skill_name)
        if not manifest:
            return False
        
        skill = Skill(
            name=manifest["name"],
            display_name=manifest["display_name"],
            description=manifest["description"],
            version=manifest["version"],
            dependencies=manifest.get("dependencies", []),
            required_apis=manifest.get("required_apis", []),
            available_tools=manifest.get("available_tools", []),
            instructions=manifest["instructions"],
            config=manifest.get("config", {}),
            is_core=manifest.get("is_core", False),
            priority=manifest.get("priority", 0)
        )
        
        # Load module
        skill.skill_module = self.load_skill_module(skill_name)
        
        # Register
        success = self.register_skill(skill)
        return success
    
    def create_skill(
        self,
        name: str,
        display_name: str,
        description: str,
        version: str = "1.0.0",
        dependencies: List[str] = None,
        required_apis: List[str] = None,
        available_tools: List[str] = None,
        instructions: str = "",
        config: Dict = None,
        is_core: bool = False,
        priority: int = 0
    ) -> Skill:
        """Create a new skill programmatically."""
        skill = Skill(
            name=name,
            display_name=display_name,
            description=description,
            version=version,
            dependencies=dependencies or [],
            required_apis=required_apis or [],
            available_tools=available_tools or [],
            instructions=instructions,
            config=config or {},
            is_core=is_core,
            priority=priority
        )
        
        self.register_skill(skill)
        return skill
    
    def update_skill(self, name: str, **kwargs) -> bool:
        """Update skill properties."""
        if name not in self._skills:
            return False
        
        skill = self._skills[name]
        for key, value in kwargs.items():
            if hasattr(skill, key) and key not in ("name", "created_at"):
                setattr(skill, key, value)
        
        skill.updated_at = datetime.utcnow()
        return True
    
    def remove_skill(self, name: str) -> bool:
        """Remove a skill."""
        if name not in self._skills:
            return False
        
        skill = self._skills[name]
        
        # Deactivate if active
        if skill.status == SkillStatus.ACTIVE:
            self.deactivate_skill(name)
        
        # Call cleanup hook if exists
        if skill.skill_module and hasattr(skill.skill_module, "on_remove"):
            try:
                skill.skill_module.on_remove()
            except Exception:
                pass
        
        del self._skills[name]
        return True
    
    def save_skill_manifest(self, skill: Skill) -> bool:
        """Save skill manifest to SKILL.md."""
        skill_path = self.skills_dir / skill.name
        skill_path.mkdir(parents=True, exist_ok=True)
        
        skill_md = skill_path / "SKILL.md"
        
        # Create frontmatter
        frontmatter = {
            "name": skill.name,
            "display_name": skill.display_name,
            "description": skill.description,
            "version": skill.version,
            "dependencies": skill.dependencies,
            "required_apis": skill.required_apis,
            "available_tools": skill.available_tools,
            "config": skill.config,
            "is_core": skill.is_core,
            "priority": skill.priority
        }
        
        import yaml
        content = "---\n"
        content += yaml.dump(frontmatter, default_flow_style=False)
        content += "---\n\n"
        content += skill.instructions
        
        skill_md.write_text(content, encoding="utf-8")
        return True
    
    def export_skill(self, name: str, export_path: Path) -> bool:
        """Export a skill to a directory."""
        skill = self._skills.get(name)
        if not skill:
            return False
        
        export_path.mkdir(parents=True, exist_ok=True)
        
        # Save manifest
        manifest = skill.to_dict()
        manifest["instructions"] = skill.instructions
        
        import yaml
        (export_path / "SKILL.md").write_text(
            "---\n" + yaml.dump({k: v for k, v in manifest.items() if k != "instructions"}, default_flow_style=False) + "---\n\n" + skill.instructions,
            encoding="utf-8"
        )
        
        # Copy skill.py if exists
        skill_py = self.skills_dir / name / "skill.py"
        if skill_py.exists():
            import shutil
            shutil.copy2(skill_py, export_path / "skill.py")
        
        return True


# Global skill registry instance
_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry instance."""
    global _skill_registry
    if _skill_registry is None:
        settings = get_settings()
        _skill_registry = SkillRegistry(settings.skills.skills_dir)
    return _skill_registry


async def initialize_skills() -> Dict[str, bool]:
    """Initialize all skills."""
    registry = get_skill_registry()
    return registry.load_all_skills(auto_activate=True)