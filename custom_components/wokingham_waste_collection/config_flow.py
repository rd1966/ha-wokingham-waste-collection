"""Config flow for Wokingham Bin Collection Tracker integration."""
import logging
import re
import voluptuous as vol
import requests
from bs4 import BeautifulSoup

from homeassistant import config_entries
from homeassistant.core import callback

DOMAIN = "wokingham_waste_collection"
_LOGGER = logging.getLogger(__name__)

class WokinghamWasteCollectionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wokingham Bins."""

    VERSION = 1

    def __init__(self):
        """Initialize the flow storage."""
        self.postcode = None
        self.addresses = {}  # Format: {"12 High Street": "100012345"}

    async def async_step_user(self, user_input=None):
        """Step 1: Ask the user for their postcode and fetch matching addresses."""
        errors = {}

        if user_input is not None:
            self.postcode = user_input["postcode"].strip().lower()
            
            # Fetch the addresses from the council website
            try:
                # Use hass.async_add_executor_job to prevent requests from blocking HA thread
                self.addresses = await self.hass.async_add_executor_job(
                    self._fetch_addresses_by_postcode, self.postcode
                )
                
                if not self.addresses:
                    errors["base"] = "no_addresses_found"
                else:
                    # Successfully fetched addresses, proceed to dropdown step
                    return await self.async_step_address()
                    
            except Exception as e:
                _LOGGER.error("Failed to fetch addresses for postcode %s: %s", self.postcode, e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("postcode"): str}),
            errors=errors,
        )

    async def async_step_address(self, user_input=None):
        """Step 2: Present a dropdown of matching text addresses to select from."""
        errors = {}

        if user_input is not None:
            selected_text = user_input["address_text"]
            selected_id = self.addresses[selected_text]

            return self.async_create_entry(
                title=f"Bins ({selected_text})",
                data={
                    "postcode": self.postcode,
                    "address_id": selected_id,
                },
            )

        # Build a dropdown selection layout out of our dictionary keys
        address_list = list(self.addresses.keys())
        data_schema = vol.Schema({
            vol.Required("address_text"): vol.In(address_list)
        })

        return self.async_show_form(
            step_id="address",
            data_schema=data_schema,
            errors=errors,
        )

    def _fetch_addresses_by_postcode(self, postcode):
        """Synchronous scrap scraper helper running on executor thread pool."""
        url = "https://www.wokingham.gov.uk/rubbish-and-recycling/waste-collection/find-your-bin-collection-day"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        address_map = {}

        session = requests.Session()
        
        # Step A: Hit landing page to steal security form token
        res1 = session.get(url, headers=headers, timeout=10)
        soup1 = BeautifulSoup(res1.text, 'html.parser')
        token1 = soup1.find("input", {"name": "form_build_id"})['value']

        # Step B: Submit Postcode to populate address options list
        payload1 = {
            "postcode_search": postcode,
            "op": "Find Address",
            "form_build_id": token1,
            "form_id": "waste_collection_api_form"
        }
        res2 = session.post(url, data=payload1, headers=headers, timeout=10)
        soup2 = BeautifulSoup(res2.text, 'html.parser')

        # Step C: Parse select box dropdown choices
        select_box = soup2.find("select", {"name": "address_options"})
        if select_box:
            options = select_box.find_all("option")
            for option in options:
                val = option.get("value")
                text = option.get_text().strip()
                # Skip placeholder options like '- Select an address -'
                if val and val != "" and "select" not in text.lower():
                    address_map[text] = val

        return address_map