from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

SENSORS = (
    ("today_energy", "Расход за сегодня", "today_kwh", "kWh", "measurement"),
    ("today_cost", "Стоимость за сегодня", "today_cost", "₽", "measurement"),
    ("month_energy", "Расход за месяц", "month_kwh", "kWh", "measurement"),
    ("month_cost", "Стоимость за месяц", "month_cost", "₽", "measurement"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        ElectroUchetSensor(coordinator, entry, *description) for description in SENSORS
    )


class ElectroUchetSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, name, value_key, unit, state_class):
        super().__init__(coordinator)
        self._value_key = value_key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass(state_class)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name="ЭлектроУчёт",
            manufacturer="ЭлектроУчёт", model="Учёт электроэнергии",
        )

    @property
    def native_value(self):
        return self.coordinator.data.get(self._value_key, 0)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        return {
            "тариф_руб_за_кВтч": data.get("tariff"),
            "показание_счетчика": data.get("last_value"),
            "последнее_обновление": data.get("last_seen"),
            "история_по_дням": data.get("daily_history", []),
            "история_по_месяцам": data.get("monthly_history", []),
            "изменение_к_прошлому_месяцу_проц": data.get("month_change_percent"),
        }
