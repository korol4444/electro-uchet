from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_SOURCE, CONF_TARIFF, DEFAULT_TARIFF, DOMAIN


class ElectroUchetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            entity_id = user_input[CONF_SOURCE]
            state = self.hass.states.get(entity_id)
            if state is None:
                errors["base"] = "entity_not_found"
            else:
                try:
                    value = float(state.state)
                    if value < 0:
                        raise ValueError
                except (ValueError, TypeError):
                    errors["base"] = "invalid_sensor"
                else:
                    await self.async_set_unique_id(entity_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"ЭлектроУчёт — {entity_id}", data=user_input
                    )

        schema = vol.Schema({
            vol.Required(CONF_SOURCE): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_TARIFF, default=DEFAULT_TARIFF): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100000, step=0.01, mode="box")
            ),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ElectroUchetOptionsFlow(config_entry)


class ElectroUchetOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        tariff = self.config_entry.options.get(
            CONF_TARIFF, self.config_entry.data.get(CONF_TARIFF, DEFAULT_TARIFF)
        )
        schema = vol.Schema({
            vol.Required(CONF_TARIFF, default=tariff): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100000, step=0.01, mode="box")
            ),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
