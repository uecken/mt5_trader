"""
Thought input module.
Manages trader thought/reasoning input via web interface.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Callable
from pathlib import Path
import json
import logging
import asyncio
from collections import deque

from models.market_data import Action, ThoughtInput

logger = logging.getLogger(__name__)


class ThoughtManager:
    """
    Manages trader thoughts and pending action notifications.
    Works with web interface for thought input.
    """

    def __init__(
        self,
        storage_dir: Path,
        on_thought_received: Optional[Callable[[ThoughtInput], None]] = None
    ):
        """
        Initialize the thought manager.

        Args:
            storage_dir: Directory to store thought logs
            on_thought_received: Callback when thought is received
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.on_thought_received = on_thought_received

        # Queue of pending actions waiting for thoughts
        self._pending_actions: deque = deque(maxlen=10)
        # Stored thoughts
        self._thoughts: List[ThoughtInput] = []
        # Event for notifying web clients
        self._action_events: List[asyncio.Event] = []

    def add_pending_action(self, action: Action, timestamp: Optional[datetime] = None):
        """
        Add a pending action that needs thought input.

        Args:
            action: The trading action that occurred
            timestamp: When the action occurred
        """
        pending = {
            "action": action,
            "timestamp": timestamp or datetime.now(timezone.utc),
            "thought": None
        }
        self._pending_actions.append(pending)
        logger.info(f"Pending action added: {action.value}")

        # Notify any waiting clients
        for event in self._action_events:
            event.set()

    def get_pending_actions(self) -> List[Dict]:
        """
        Get list of actions waiting for thought input.

        Returns:
            List of pending action dictionaries
        """
        return [
            {
                "action": p["action"].value,
                "timestamp": p["timestamp"].isoformat(),
                "thought": p["thought"]
            }
            for p in self._pending_actions
            if p["thought"] is None
        ]

    def submit_thought(
        self,
        thought_text: str,
        action: Action,
        timestamp: Optional[datetime] = None
    ) -> ThoughtInput:
        """
        Submit a thought for an action.

        Args:
            thought_text: The trader's reasoning/thought
            action: The action this thought is for
            timestamp: When this thought was submitted

        Returns:
            ThoughtInput object
        """
        thought = ThoughtInput(
            thought=thought_text,
            action=action,
            timestamp=timestamp or datetime.now(timezone.utc)
        )

        # Find and update pending action
        for pending in self._pending_actions:
            if pending["action"] == action and pending["thought"] is None:
                pending["thought"] = thought_text
                break

        # Store the thought
        self._thoughts.append(thought)
        self._save_thought(thought)

        logger.info(f"Thought submitted for {action.value}: {thought_text[:50]}...")

        # Trigger callback
        if self.on_thought_received:
            self.on_thought_received(thought)

        return thought

    def _save_thought(self, thought: ThoughtInput):
        """Save thought to storage."""
        timestamp_str = thought.timestamp.strftime("%Y%m%d_%H%M%S") if thought.timestamp else datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp_str}_{thought.action.value}.json"
        filepath = self.storage_dir / filename

        data = {
            "thought": thought.thought,
            "action": thought.action.value,
            "timestamp": thought.timestamp.isoformat() if thought.timestamp else None
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.debug(f"Thought saved: {filepath}")

    def get_recent_thoughts(self, limit: int = 10) -> List[ThoughtInput]:
        """
        Get recent thoughts.

        Args:
            limit: Maximum number of thoughts to return

        Returns:
            List of ThoughtInput objects
        """
        return self._thoughts[-limit:]

    def load_thoughts_from_storage(self) -> List[ThoughtInput]:
        """Load thoughts from storage directory."""
        thoughts = []
        for filepath in sorted(self.storage_dir.glob("*.json")):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                thought = ThoughtInput(
                    thought=data.get("thought", ""),
                    action=Action(data.get("action", "HOLD")),
                    timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None
                )
                thoughts.append(thought)
            except Exception as e:
                logger.error(f"Error loading thought from {filepath}: {e}")

        self._thoughts = thoughts
        return thoughts

    async def wait_for_action(self, timeout: float = 60.0) -> bool:
        """
        Wait for a new action to occur (for web clients).

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if action occurred, False if timeout
        """
        event = asyncio.Event()
        self._action_events.append(event)

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            self._action_events.remove(event)

    def clear_pending_actions(self):
        """Clear all pending actions."""
        self._pending_actions.clear()


if __name__ == "__main__":
    # Test the thought manager
    logging.basicConfig(level=logging.INFO)

    manager = ThoughtManager(storage_dir=Path("data/thoughts"))

    # Add a pending action
    manager.add_pending_action(Action.BUY)

    # Get pending
    print("Pending actions:", manager.get_pending_actions())

    # Submit thought
    thought = manager.submit_thought(
        thought_text="RSI showed oversold condition, price bounced from support level",
        action=Action.BUY
    )
    print(f"Thought submitted: {thought}")

    # Check pending again
    print("Pending actions after submit:", manager.get_pending_actions())
