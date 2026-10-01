from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CandidateRegistry:
    cooldown_blocks: int = 20
    max_failed_attempts_per_token: int = 2
    seen_pools: set[str] = field(default_factory=set)
    last_attempt_block: dict[str, int] = field(default_factory=dict)
    failed_attempts: dict[str, int] = field(default_factory=dict)

    def is_duplicate_pool(self, pool: str) -> bool:
        return pool.lower() in self.seen_pools

    def mark_pool_seen(self, pool: str) -> None:
        self.seen_pools.add(pool.lower())

    def can_attempt(self, token: str, current_block: int) -> tuple[bool, str]:
        t = token.lower()
        fails = int(self.failed_attempts.get(t, 0))
        if fails >= int(self.max_failed_attempts_per_token):
            return False, "REJECT: token failure limit reached"

        last = self.last_attempt_block.get(t)
        if last is not None and int(current_block) - int(last) < int(self.cooldown_blocks):
            return False, "REJECT: token cooldown active"
        return True, "PASS"

    def record_attempt(self, token: str, current_block: int, success: bool) -> None:
        t = token.lower()
        self.last_attempt_block[t] = int(current_block)
        if success:
            self.failed_attempts[t] = 0
        else:
            self.failed_attempts[t] = int(self.failed_attempts.get(t, 0)) + 1
