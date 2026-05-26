"""Config flow for Wokingham Bin Collection Tracker integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

DOMAIN = "DOMAIN = "wokingham_waste_collection"

_LOGGER = logging.getLogger(__name__)

class WokinghamBinsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wokingham Bins."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step where the user inputs data."""
        errors = {}

        if user_input is not None:
            # Basic validation to ensure fields aren't completely blank
            if not user_input.get("postcode") or not user_input.get("address_id"):
                errors["base"] = "invalid_auth"
            else:
                # Clean up spacing on postcode data
                user_input["postcode"] = user_input["postcode"].strip().lower()
                user_input["address_id"] = user_input["address_id"].strip()

                return self.async_create_entry(
                    title=f"Bins ({user_input['postcode'].upper()})", 
                    data=user_input
                )

        # Defines the visual text boxes shown to the user in the UI popup
        data_schema = vol.Schema(
            {
                vol.Required("postcode"): str,
                vol.Required("address_id"): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
