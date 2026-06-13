import logging
from datetime import datetime, timedelta
import re
import requests
from bs4 import BeautifulSoup

from homeassistant.components.sensor import SensorEntity

DOMAIN = "wokingham_waste_collection"
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(hours=6)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the bin sensors dynamically from config entry data."""
    postcode = entry.data.get("postcode")
    address_id = entry.data.get("address_id")
    
    categories = ["household_waste", "recycling", "food_waste", "garden_waste"]
    sensors = [WokinghamBinSensor(category, postcode, address_id) for category in categories]
    
    async_add_entities(sensors, True)

class WokinghamBinSensor(SensorEntity):
    """Representation of a Wokingham Bin Sensor."""

    def __init__(self, bin_type, postcode, address_id):
        self._bin_type = bin_type
        self._postcode = postcode
        self._address_id = address_id
        self._state = None
        self._attributes = {}
        self._name = f"Wokingham {bin_type.replace('_', ' ').title()}"
        self._unique_id = f"wokingham_{address_id}_{bin_type}"

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def icon(self):
        """WOW ITEM #2: Dynamic, contextual icons matching the bin type."""
        if self._bin_type == "recycling":
            return "mdi:recycle"
        elif self._bin_type == "food_waste":
            return "mdi:food-apple"
        elif self._bin_type == "garden_waste":
            return "mdi:leaf"
        return "mdi:trash-can"

    def update(self):
        """Fetch live data from the council website."""
        url = "https://www.wokingham.gov.uk/rubbish-and-recycling/waste-collection/find-your-bin-collection-day"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        
        try:
            session = requests.Session()
            
            res1 = session.get(url, headers=headers, timeout=10)
            token1 = BeautifulSoup(res1.text, 'html.parser').find("input", {"name": "form_build_id"})['value']

            payload1 = {"postcode_search": self._postcode, "op": "Find Address", "form_build_id": token1, "form_id": "waste_collection_api_form"}
            res2 = session.post(url, data=payload1, headers=headers, timeout=10)
            token2 = BeautifulSoup(res2.text, 'html.parser').find("input", {"name": "form_build_id"})['value']

            payload2 = {"postcode_search": self._postcode, "address_options": self._address_id, "op": "Show collection dates", "form_build_id": token2, "form_id": "waste_collection_api_form"}
            res3 = session.post(url, data=payload2, headers=headers, timeout=10)

            if res3.status_code == 200:
                soup = BeautifulSoup(res3.text, 'html.parser')
                container = soup.find(id="main-content")
                if container:
                    text_lines = [line.strip() for line in container.get_text().split('\n') if line.strip()]
                    today = datetime.now().date()
                    
                    for i, line in enumerate(text_lines):
                        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
                        if date_match:
                            date_str = date_match.group(1)
                            
                            matched_bin = "unknown"
                            for check_index in range(i-1, -1, -1):
                                pos_name = text_lines[check_index].lower()
                                if any(k in pos_name for k in ["waste", "recycling", "household"]):
                                    if "regular" not in pos_name and "next" not in pos_name:
                                        matched_bin = pos_name.replace(" (week 1)", "").replace(" (week 2)", "").strip().replace(" ", "_")
                                        break
                            
                            if matched_bin == self._bin_type:
                                collection_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                                days_until = (collection_date - today).days
                                days_until = max(0, days_until)
                                
                                # WOW ITEM #1: Human-readable states + raw days in attributes for easy automation
                                if days_until == 0:
                                    self._state = "Today"
                                elif days_until == 1:
                                    self._state = "Tomorrow"
                                else:
                                    self._state = f"{days_until} days"
                                    
                                self._attributes = {
                                    "collection_date": date_str,
                                    "days_until": days_until,
                                    "is_collection_imminent": days_until <= 1
                                }
                                return
        except Exception as e:
            _LOGGER.error("Error updating Wokingham Bin data: %s", e)