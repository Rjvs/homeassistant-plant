"""Tests for the Daily Light Integral functionality."""
from datetime import datetime, timedelta
import unittest
from unittest.mock import MagicMock, patch

from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from custom_components.plant.plant_meters import PlantDailyLightIntegral


class TestDailyLightIntegral(unittest.TestCase):
    """Test the Daily Light Integral calculation."""

    def setUp(self):
        """Set up test variables."""
        self.hass = MagicMock()
        self.config = MagicMock()
        self.config.entry_id = "test_entry_id"
        self.config.data = {"plant_info": {"name": "Test Plant"}}
        self.illuminance_sensor = MagicMock()
        self.illuminance_sensor.entity_id = "sensor.test_ppfd_integral"
        self.plant_device = MagicMock()
        self.plant_device.unique_id = "test_plant_unique_id"
        
        # Create the DLI sensor
        self.dli = PlantDailyLightIntegral(
            self.hass, self.config, self.illuminance_sensor, self.plant_device
        )
        
        # Mock the async_write_ha_state method
        self.dli.async_write_ha_state = MagicMock()

    def test_initialization(self):
        """Test that the sensor initializes with correct values."""
        self.assertEqual(self.dli._attr_native_value, 0)
        self.assertEqual(self.dli._data_points, [])
        self.assertEqual(self.dli._source_entity, "sensor.test_ppfd_integral")

    def test_source_changed_valid_increment(self):
        """Test that source changes with valid increments are recorded."""
        # Create a mock event with new state = 10, old state = 5
        event = MagicMock()
        event.data = {
            "new_state": MagicMock(state="10"),
            "old_state": MagicMock(state="5")
        }
        
        # Call the source changed method
        self.dli._source_changed(event)
        
        # Check that a data point was added
        self.assertEqual(len(self.dli._data_points), 1)
        self.assertEqual(self.dli._data_points[0][1], 5)  # Increment value
        self.assertEqual(self.dli._attr_native_value, 5)
        
        # Add another increment
        event.data = {
            "new_state": MagicMock(state="15"),
            "old_state": MagicMock(state="10")
        }
        self.dli._source_changed(event)
        
        # Check that another data point was added and value updated
        self.assertEqual(len(self.dli._data_points), 2)
        self.assertEqual(self.dli._attr_native_value, 10)  # 5 + 5

    def test_source_changed_invalid_states(self):
        """Test handling of invalid states."""
        # Test with unknown state
        event = MagicMock()
        event.data = {
            "new_state": MagicMock(state=STATE_UNKNOWN),
            "old_state": MagicMock(state="5")
        }
        self.dli._source_changed(event)
        self.assertEqual(len(self.dli._data_points), 0)
        
        # Test with unavailable state
        event.data = {
            "new_state": MagicMock(state=STATE_UNAVAILABLE),
            "old_state": MagicMock(state="5")
        }
        self.dli._source_changed(event)
        self.assertEqual(len(self.dli._data_points), 0)
        
        # Test with non-numeric state
        event.data = {
            "new_state": MagicMock(state="not_a_number"),
            "old_state": MagicMock(state="5")
        }
        self.dli._source_changed(event)
        self.assertEqual(len(self.dli._data_points), 0)

    def test_update_sliding_window(self):
        """Test that old data points are removed from the sliding window."""
        # Add some data points with timestamps
        now = datetime.now()
        old_time = now - timedelta(hours=25)  # Older than 24 hours
        recent_time = now - timedelta(hours=12)  # Within 24 hours
        
        self.dli._data_points = [
            (old_time, 5),      # Should be removed
            (recent_time, 10),  # Should be kept
            (now, 15)           # Should be kept
        ]
        
        # Update the sliding window
        with patch('custom_components.plant.plant_meters.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            self.dli._update_sliding_window()
        
        # Check that old data point was removed
        self.assertEqual(len(self.dli._data_points), 2)
        self.assertEqual(self.dli._data_points[0][1], 10)
        self.assertEqual(self.dli._data_points[1][1], 15)
        self.assertEqual(self.dli._attr_native_value, 25)  # 10 + 15

    def test_empty_data_points(self):
        """Test behavior with empty data points."""
        self.dli._data_points = []
        self.dli._update_value()
        self.assertEqual(self.dli._attr_native_value, 0)

    def test_negative_increments_ignored(self):
        """Test that negative increments are ignored."""
        event = MagicMock()
        event.data = {
            "new_state": MagicMock(state="5"),
            "old_state": MagicMock(state="10")  # Decreasing value
        }
        
        self.dli._source_changed(event)
        self.assertEqual(len(self.dli._data_points), 0)  # No data point added

    def test_rounding(self):
        """Test that values are properly rounded."""
        self.dli._data_points = [
            (datetime.now(), 5.123),
            (datetime.now(), 10.456)
        ]
        self.dli._update_value()
        self.assertEqual(self.dli._attr_native_value, 15.58)  # 5.123 + 10.456 = 15.579 rounded to 15.58
