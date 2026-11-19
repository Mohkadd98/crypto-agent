"""
Skill lifecycle hooks.
"""

def on_activate(config: dict):
    """Called when the skill is activated."""
    print(f"[Skill] Activated with config: {config}")


def on_deactivate():
    """Called when the skill is deactivated."""
    print("[Skill] Deactivated")


def on_remove():
    """Called when the skill is removed."""
    print("[Skill] Removed")
