"""Meter entities for the plant integration"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.integration.const import METHOD_TRAPEZOIDAL
from homeassistant.components.integration.sensor import IntegrationSensor
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    LIGHT_LUX,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfConductivity,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    ATTR_CONDUCTIVITY,
    DATA_UPDATED,
    DEFAULT_LUX_TO_PPFD,
    DOMAIN,
    FLOW_PLANT_INFO,
    FLOW_SENSOR_CONDUCTIVITY,
    FLOW_SENSOR_HUMIDITY,
    FLOW_SENSOR_ILLUMINANCE,
    FLOW_SENSOR_MOISTURE,
    FLOW_SENSOR_TEMPERATURE,
    READING_CONDUCTIVITY,
    READING_DLI,
    READING_HUMIDITY,
    READING_ILLUMINANCE,
    READING_MOISTURE,
    READING_PPFD,
    READING_TEMPERATURE,
    UNIT_DLI,
    UNIT_PPFD,
)

_LOGGER = logging.getLogger(__name__)


class PlantCurrentStatus(RestoreSensor):
    """Parent class for the meter classes below"""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, plantdevice: Entity
    ) -> None:
        """Initialize the Plant component."""
        self._hass = hass
        self._config = config
        self._default_state = 0
        self._plant = plantdevice
        # self._conf_check_days = self._plant.check_days
        self.entity_id = async_generate_entity_id(
            f"{DOMAIN}.{{}}", self.name, current_ids={}
        )
        if not self._attr_native_value or self._attr_native_value == STATE_UNKNOWN:
            self._attr_native_value = self._default_state

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self) -> dict:
        if self._external_sensor:
            attributes = {
                "external_sensor": self.external_sensor,
                # "history_max": self._history.max,
                # "history_min": self._history.min,
            }
            return attributes

    @property
    def external_sensor(self) -> str:
        """The external sensor we are tracking"""
        return self._external_sensor

    def replace_external_sensor(self, new_sensor: str | None) -> None:
        """Modify the external sensor"""
        _LOGGER.info("Setting %s external sensor to %s", self.entity_id, new_sensor)
        # pylint: disable=attribute-defined-outside-init
        self._external_sensor = new_sensor
        async_track_state_change_event(
            self._hass,
            list([self.entity_id, self._external_sensor]),
            self._state_changed_event,
        )

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()

        # We do not restore the state for these they are read from the external sensor anyway
        self._attr_native_value = STATE_UNKNOWN
        if state:
            if "external_sensor" in state.attributes:
                self.replace_external_sensor(state.attributes["external_sensor"])
        tracker = [self.entity_id]
        if self._external_sensor:
            tracker.append(self._external_sensor)
        async_track_state_change_event(
            self._hass,
            tracker,
            self._state_changed_event,
        )
        async_dispatcher_connect(
            self._hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    @callback
    def _state_changed_event(self, event):
        """Sensor state change event."""
        self.state_changed(event.data.get("entity_id"), event.data.get("new_state"))

    @callback
    def state_changed(self, entity_id, new_state):
        """Run on every update to allow for changes from the GUI and service call"""
        if not self.hass.states.get(self.entity_id):
            return
        current_attrs = self.hass.states.get(self.entity_id).attributes
        if current_attrs.get("external_sensor") != self._external_sensor:
            self.replace_external_sensor(current_attrs.get("external_sensor"))
        if self._external_sensor:
            external_sensor = self.hass.states.get(self._external_sensor)
            if external_sensor:
                self._attr_native_value = external_sensor.state
                self._attr_native_unit_of_measurement = external_sensor.attributes[
                    ATTR_UNIT_OF_MEASUREMENT
                ]
            else:
                self._attr_native_value = STATE_UNKNOWN
        else:
            self._attr_native_value = STATE_UNKNOWN

        if self.state == STATE_UNKNOWN or self.state is None:
            return


class PlantCurrentIlluminance(PlantCurrentStatus):
    """Entity class for the current illuminance meter"""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, plantdevice: Entity
    ) -> None:
        """Initialize the sensor"""
        self._attr_name = (
            f"{config.data[FLOW_PLANT_INFO][ATTR_NAME]} {READING_ILLUMINANCE}"
        )
        self._attr_unique_id = f"{config.entry_id}-current-illuminance"
        self._attr_icon = "mdi:brightness-6"
        self._external_sensor = config.data[FLOW_PLANT_INFO].get(
            FLOW_SENSOR_ILLUMINANCE
        )
        self._attr_native_unit_of_measurement = LIGHT_LUX

        _LOGGER.info(
            "Added external sensor for %s %s", self.entity_id, self._external_sensor
        )
        super().__init__(hass, config, plantdevice)

    @property
    def device_class(self) -> str:
        """Device class"""
        return SensorDeviceClass.ILLUMINANCE


class PlantCurrentConductivity(PlantCurrentStatus):
    """Entity class for the current conductivity meter"""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, plantdevice: Entity
    ) -> None:
        """Initialize the sensor"""
        self._attr_name = (
            f"{config.data[FLOW_PLANT_INFO][ATTR_NAME]} {READING_CONDUCTIVITY}"
        )
        self._attr_unique_id = f"{config.entry_id}-current-conductivity"
        self._attr_icon = "mdi:spa-outline"
        self._external_sensor = config.data[FLOW_PLANT_INFO].get(
            FLOW_SENSOR_CONDUCTIVITY
        )
        self._attr_native_unit_of_measurement = UnitOfConductivity.MICROSIEMENS_PER_CM

        super().__init__(hass, config, plantdevice)

    @property
    def device_class(self) -> None:
        """Device class - not defined for conductivity"""
        return ATTR_CONDUCTIVITY


class PlantCurrentMoisture(PlantCurrentStatus):
    """Entity class for the current moisture meter"""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, plantdevice: Entity
    ) -> None:
        """Initialize the sensor"""
        self._attr_name = (
            f"{config.data[FLOW_PLANT_INFO][ATTR_NAME]} {READING_MOISTURE}"
        )
        self._attr_unique_id = f"{config.entry_id}-current-moisture"
        self._external_sensor = config.data[FLOW_PLANT_INFO].get(FLOW_SENSOR_MOISTURE)
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:water"

        super().__init__(hass, config, plantdevice)

    @property
    def device_class(self) -> str:
        """Device class"""
        return SensorDeviceClass.HUMIDITY


class PlantCurrentTemperature(PlantCurrentStatus):
    """Entity class for the current temperature meter"""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, plantdevice: Entity
    ) -> None:
        """Initialize the sensor"""
        self._attr_name = (
            f"{config.data[FLOW_PLANT_INFO][ATTR_NAME]} {READING_TEMPERATURE}"
        )
        self._attr_unique_id = f"{config.entry_id}-current-temperature"
        self._external_sensor = config.data[FLOW_PLANT_INFO].get(
            FLOW_SENSOR_TEMPERATURE
        )
        self._attr_icon = "mdi:thermometer"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        super().__init__(hass, config, plantdevice)

    @property
    def device_class(self) -> str:
        """Device class"""
        return SensorDeviceClass.TEMPERATURE


class PlantCurrentHumidity(PlantCurrentStatus):
    """Entity class for the current humidity meter"""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, plantdevice: Entity
    ) -> None:
        """Initialize the sensor"""
        self._attr_name = (
            f"{config.data[FLOW_PLANT_INFO][ATTR_NAME]} {READING_HUMIDITY}"
        )
        self._attr_unique_id = f"{config.entry_id}-current-humidity"
        self._external_sensor = config.data[FLOW_PLANT_INFO].get(FLOW_SENSOR_HUMIDITY)
        self._attr_icon = "mdi:water-percent"
        self._attr_native_unit_of_measurement = PERCENTAGE
        super().__init__(hass, config, plantdevice)

    @property
    def device_class(self) -> str:
        """Device class"""
        return SensorDeviceClass.HUMIDITY


class PlantCurrentPpfd(PlantCurrentStatus):
    """Entity reporting current PPFD calculated from LX"""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, plantdevice: Entity
    ) -> None:
        """Initialize the sensor"""
        self._attr_name = f"{config.data[FLOW_PLANT_INFO][ATTR_NAME]} {READING_PPFD}"

        self._attr_unique_id = f"{config.entry_id}-current-ppfd"
        self._attr_unit_of_measurement = UNIT_PPFD
        self._attr_native_unit_of_measurement = UNIT_PPFD

        self._plant = plantdevice

        self._external_sensor = self._plant.sensor_illuminance.entity_id
        self._attr_icon = "mdi:white-balance-sunny"
        super().__init__(hass, config, plantdevice)

    @property
    def device_class(self) -> str:
        """Device class"""
        return SensorDeviceClass.ILLUMINANCE

    def ppfd(self, value: float | int | str) -> float | str:
        """
        Returns a calculated PPFD-value from the lx-value

        See https://community.home-assistant.io/t/light-accumulation-for-xiaomi-flower-sensor/111180/3
        https://www.apogeeinstruments.com/conversion-ppfd-to-lux/
        μmol/m²/s
        """
        if value is not None and value != STATE_UNAVAILABLE and value != STATE_UNKNOWN:
            value = float(value) * DEFAULT_LUX_TO_PPFD / 1000000

        return value

    @callback
    def state_changed(self, entity_id: str, new_state: str) -> None:
        """Run on every update to allow for changes from the GUI and service call"""
        if not self.hass.states.get(self.entity_id):
            return
        if self._external_sensor != self._plant.sensor_illuminance.entity_id:
            self.replace_external_sensor(self._plant.sensor_illuminance.entity_id)
        if self._external_sensor:
            external_sensor = self.hass.states.get(self._external_sensor)
            if external_sensor:
                self._attr_native_value = self.ppfd(external_sensor.state)
            else:
                self._attr_native_value = STATE_UNKNOWN
        else:
            self._attr_native_value = STATE_UNKNOWN


class PlantTotalLightIntegral(IntegrationSensor):
    """Entity class to calculate PPFD from LX"""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        illuminance_ppfd_sensor: Entity,
    ) -> None:
        """Initialize the sensor"""
        super().__init__(
            integration_method=METHOD_TRAPEZOIDAL,
            name=f"{config.data[FLOW_PLANT_INFO][ATTR_NAME]} Total {READING_PPFD} Integral",
            round_digits=2,
            source_entity=illuminance_ppfd_sensor.entity_id,
            unique_id=f"{config.entry_id}-ppfd-integral",
            unit_prefix=None,
            unit_time=UnitOfTime.SECONDS,
        )
        self._unit_of_measurement = UNIT_PPFD

    def _unit(self, source_unit: str) -> str:
        """Override unit"""
        return self._unit_of_measurement


class PlantDailyLightIntegral(SensorEntity):
    """Entity class to calculate Daily Light Integral from PPDF as a sliding 24-hour window"""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        illuminance_integration_sensor: Entity,
        plantdevice: Entity,
    ) -> None:
        """Initialize the sensor"""
        self._attr_name = f"{config.data[FLOW_PLANT_INFO][ATTR_NAME]} {READING_DLI}"
        self._attr_unique_id = f"{config.entry_id}-dli"
        self.entity_id = async_generate_entity_id(
            f"{DOMAIN}.{{}}", self.name, current_ids={}
        )
        
        self._hass = hass
        self._config = config
        self._plant = plantdevice
        self._source_entity = illuminance_integration_sensor.entity_id
        self._attr_native_unit_of_measurement = UNIT_DLI
        self._attr_icon = "mdi:white-balance-sunny"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        
        # Store the last 24 hours of data points (timestamp, value)
        self._data_points = []
        self._last_value = 0
        self._attr_native_value = 0

    @property
    def device_info(self) -> dict:
        """Device info for devices"""
        return {
            "identifiers": {(DOMAIN, self._plant.unique_id)},
        }
        
    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        
        # Restore previous state if available
        state = await self.async_get_last_state()
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._attr_native_value = float(state.state)
            except (ValueError, TypeError):
                self._attr_native_value = 0
                
        # Track the source entity
        async_track_state_change_event(
            self._hass,
            [self._source_entity],
            self._source_changed,
        )
        
        # Schedule regular updates to maintain the sliding window
        from homeassistant.helpers.event import async_track_time_interval
        self.async_on_remove(
            async_track_time_interval(
                self._hass,
                self._update_sliding_window,
                timedelta(minutes=5)  # Update every 5 minutes
            )
        )
        
    @callback
    def _source_changed(self, event):
        """Handle source entity state changes."""
        if not event.data.get("new_state"):
            return
            
        try:
            new_value = float(event.data["new_state"].state)
            old_value = 0
            if event.data.get("old_state") and event.data["old_state"].state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    old_value = float(event.data["old_state"].state)
                except (ValueError, TypeError):
                    pass
                    
            # Calculate the increment since last update
            increment = new_value - old_value
            if increment > 0:
                now = datetime.now()
                self._data_points.append((now, increment))
                self._update_value()
                
        except (ValueError, TypeError):
            pass
            
    @callback
    def _update_sliding_window(self, _now=None):
        """Update the sliding window by removing data points older than 24 hours."""
        if not self._data_points:
            return
            
        now = datetime.now()
        cutoff = now - timedelta(hours=24)
        
        # Remove data points older than 24 hours
        self._data_points = [dp for dp in self._data_points if dp[0] >= cutoff]
        self._update_value()
        
    def _update_value(self):
        """Update the sensor value based on the current data points."""
        if not self._data_points:
            self._attr_native_value = 0
        else:
            # Sum all increments in the sliding window
            total = sum(value for _, value in self._data_points)
            self._attr_native_value = round(total, 2)
            
        self.async_write_ha_state()
