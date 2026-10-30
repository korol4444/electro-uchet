from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, Event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_SOURCE, CONF_TARIFF, DEFAULT_TARIFF, DOMAIN, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class ElectricityCoordinator(DataUpdateCoordinator):
    """Collect cumulative meter deltas into local calendar days."""

    def __init__(self, hass: HomeAssistant, entry):
        super().__init__(hass, logger=_LOGGER, name=DOMAIN, update_interval=None)
        self.entry = entry
        self.source = entry.data[CONF_SOURCE]
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY.format(entry_id=entry.entry_id))
        self.days: dict[str, float] = {}
        self.last_value: float | None = None
        self.last_seen: str | None = None
        self.data = {}

    @property
    def tariff(self) -> float:
        return float(self.entry.options.get(
            CONF_TARIFF, self.entry.data.get(CONF_TARIFF, DEFAULT_TARIFF)
        ))

    async def async_setup(self):
        saved = await self.store.async_load() or {}
        self.days = {str(k): float(v) for k, v in saved.get("days", {}).items()}
        self.last_value = saved.get("last_value")
        self.last_seen = saved.get("last_seen")
        state = self.hass.states.get(self.source)
        if state is not None:
            try:
                current = float(state.state)
                if current >= 0:
                    if self.last_value is not None and current >= float(self.last_value):
                        delta = current - float(self.last_value)
                        if 0 <= delta <= 1000:
                            self._add_to_day(dt_util.now().date().isoformat(), delta)
                    self.last_value = current
                    self.last_seen = state.last_updated.isoformat()
            except (ValueError, TypeError):
                pass
        self._prune()
        await self._async_save()
        self._refresh_data()

    async def async_source_changed(self, event: Event):
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return
        try:
            current = float(new_state.state)
        except (ValueError, TypeError):
            return
        if current < 0:
            return
        if self.last_value is not None:
            delta = current - self.last_value
            if 0 <= delta <= 1000:
                self._add_to_day(dt_util.now().date().isoformat(), delta)
        self.last_value = current
        self.last_seen = new_state.last_updated.isoformat()
        self._prune()
        await self._async_save()
        self._refresh_data()

    def async_register_midnight_reset(self):
        return async_track_time_change(
            self.hass, self._async_midnight, hour=0, minute=0, second=0
        )

    async def _async_midnight(self, now):
        self._refresh_data()

    def _add_to_day(self, key: str, amount: float):
        self.days[key] = self.days.get(key, 0.0) + amount

    def _prune(self):
        cutoff = (dt_util.now().date() - timedelta(days=400)).isoformat()
        self.days = {k: v for k, v in self.days.items() if k >= cutoff}

    async def _async_save(self):
        await self.store.async_save({
            "days": self.days, "last_value": self.last_value, "last_seen": self.last_seen
        })

    def _refresh_data(self):
        today = dt_util.now().date().isoformat()
        month = today[:7]
        today_kwh = self.days.get(today, 0.0)
        month_rows = {}
        for day, kwh in self.days.items():
            key = day[:7]
            month_rows[key] = month_rows.get(key, 0.0) + kwh
        daily = [
            {"date": k, "kwh": round(v, 3), "cost": round(v * self.tariff, 2)}
            for k, v in sorted(self.days.items())[-365:]
        ]
        monthly = []
        for key, kwh in sorted(month_rows.items())[-13:]:
            count = sum(1 for d in self.days if d.startswith(key))
            monthly.append({
                "month": key, "kwh": round(kwh, 2), "cost": round(kwh * self.tariff, 2),
                "average_daily_kwh": round(kwh / count, 2) if count else 0,
                "days_recorded": count,
            })
        current_month_kwh = month_rows.get(month, 0.0)
        previous_key = (dt_util.now().date().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        previous_to_date = sum(
            v for k, v in self.days.items()
            if k.startswith(previous_key) and int(k[8:10]) <= dt_util.now().day
        )
        change = None
        if previous_to_date > 0:
            change = round((current_month_kwh - previous_to_date) / previous_to_date * 100, 1)
        self.data = {
            "today_kwh": round(today_kwh, 3), "today_cost": round(today_kwh * self.tariff, 2),
            "month_kwh": round(current_month_kwh, 2), "month_cost": round(current_month_kwh * self.tariff, 2),
            "tariff": self.tariff, "last_value": self.last_value, "last_seen": self.last_seen,
            "daily_history": daily, "monthly_history": monthly, "month_change_percent": change,
        }
        self.async_set_updated_data(self.data)
