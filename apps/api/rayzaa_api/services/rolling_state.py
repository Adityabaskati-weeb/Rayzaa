from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(slots=True)
class RollingFeatures:
    sender_velocity_1h: int
    receiver_velocity_1h: int
    pair_velocity_24h: int
    sender_unique_counterparties_24h: int
    amount_ratio_to_sender_avg: float
    hour_of_day: int
    is_cross_bank: int
    is_self_transfer: int
    payment_format: str


class MemoryRollingState:
    def __init__(self) -> None:
        self.sender_hour_events: dict[str, deque[datetime]] = defaultdict(deque)
        self.sender_day_events: dict[str, deque[tuple[datetime, float, str]]] = defaultdict(deque)
        self.sender_day_amount_sum: dict[str, float] = defaultdict(float)
        self.sender_counterparty_counts: dict[str, dict[str, int]] = defaultdict(dict)
        self.receiver_hour_events: dict[str, deque[datetime]] = defaultdict(deque)
        self.pair_day_events: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)

    @staticmethod
    def _trim_time_only(events: deque[datetime], cutoff: datetime) -> None:
        while events and events[0] < cutoff:
            events.popleft()

    def _trim_sender(self, account_id: str, one_hour_cutoff: datetime, day_cutoff: datetime) -> None:
        sender_hour = self.sender_hour_events[account_id]
        sender_day = self.sender_day_events[account_id]
        counterparty_counts = self.sender_counterparty_counts[account_id]

        self._trim_time_only(sender_hour, one_hour_cutoff)
        while sender_day and sender_day[0][0] < day_cutoff:
            _, amount, counterparty_id = sender_day.popleft()
            self.sender_day_amount_sum[account_id] -= amount
            current_count = counterparty_counts.get(counterparty_id, 0) - 1
            if current_count <= 0:
                counterparty_counts.pop(counterparty_id, None)
            else:
                counterparty_counts[counterparty_id] = current_count

    def record(
        self,
        *,
        account_id: str,
        counterparty_id: str,
        amount: float,
        payment_format: str,
        timestamp: datetime,
        from_bank: str = "",
        to_bank: str = "",
    ) -> RollingFeatures:
        one_hour_cutoff = timestamp - timedelta(hours=1)
        twenty_four_hour_cutoff = timestamp - timedelta(hours=24)

        self._trim_sender(account_id, one_hour_cutoff, twenty_four_hour_cutoff)
        receiver_hour = self.receiver_hour_events[counterparty_id]
        pair_day = self.pair_day_events[(account_id, counterparty_id)]
        self._trim_time_only(receiver_hour, one_hour_cutoff)
        self._trim_time_only(pair_day, twenty_four_hour_cutoff)

        sender_day = self.sender_day_events[account_id]
        sender_hour = self.sender_hour_events[account_id]
        sender_avg = (
            self.sender_day_amount_sum[account_id] / len(sender_day)
            if sender_day
            else amount
        )
        amount_ratio = round(amount / max(sender_avg, 1.0), 4)
        counterparty_counts = self.sender_counterparty_counts[account_id]

        is_cross_bank = int(bool(from_bank) and bool(to_bank) and from_bank != to_bank)
        is_self_transfer = int(bool(from_bank) and bool(to_bank) and from_bank == to_bank and account_id == counterparty_id)

        features = RollingFeatures(
            sender_velocity_1h=len(sender_hour) + 1,
            receiver_velocity_1h=len(receiver_hour) + 1,
            pair_velocity_24h=len(pair_day) + 1,
            sender_unique_counterparties_24h=len(counterparty_counts) + int(counterparty_id not in counterparty_counts),
            amount_ratio_to_sender_avg=amount_ratio,
            hour_of_day=timestamp.hour,
            is_cross_bank=is_cross_bank,
            is_self_transfer=is_self_transfer,
            payment_format=payment_format,
        )

        sender_hour.append(timestamp)
        receiver_hour.append(timestamp)
        pair_day.append(timestamp)
        sender_day.append((timestamp, amount, counterparty_id))
        self.sender_day_amount_sum[account_id] += amount
        counterparty_counts[counterparty_id] = counterparty_counts.get(counterparty_id, 0) + 1

        return features
