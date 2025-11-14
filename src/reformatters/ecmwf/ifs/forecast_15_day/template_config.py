"""Template configuration for ECMWF IFS 15-day forecast."""

from typing import Any

import numpy as np
import pandas as pd
import xarray as xr
from numcodecs import Blosc

from reformatters.common.template_config import TemplateConfig


class EcmwfIfsForecast15DayTemplateConfig(TemplateConfig):
    """Template configuration for ECMWF IFS 15-day high-resolution forecast.

    Dataset specifications:
    - Resolution: 0.25° (~25 km)
    - Coverage: Global (90°N to 90°S, 0°E to 359.75°E)
    - Temporal: 3-hourly (0-144h), 6-hourly (150-360h)
    - Dimensions: (init_time, lead_time, latitude, longitude)
    """

    def dimension_coordinates(self) -> dict[str, xr.Variable]:
        """Define dimensional coordinates."""
        # Latitude: 90°N to 90°S at 0.25° resolution
        lat = np.arange(90, -90.25, -0.25)

        # Longitude: 0°E to 359.75°E at 0.25° resolution
        lon = np.arange(0, 360, 0.25)

        # Lead time: 3-hourly to 144h, then 6-hourly to 360h
        lead_time_3h = np.arange(0, 147, 3)  # 0, 3, 6, ..., 144
        lead_time_6h = np.arange(150, 366, 6)  # 150, 156, ..., 360
        lead_time_hours = np.concatenate([lead_time_3h, lead_time_6h])
        lead_time = pd.to_timedelta(lead_time_hours, unit="h")

        # Init time: placeholder for template (will be filled during updates)
        # Start with a reference time
        init_time = pd.date_range("2025-01-01T00:00:00", periods=1, freq="6h")

        return {
            "init_time": xr.Variable(
                ("init_time",),
                init_time,
                attrs={
                    "long_name": "Forecast initialization time",
                    "standard_name": "forecast_reference_time",
                },
            ),
            "lead_time": xr.Variable(
                ("lead_time",),
                lead_time,
                attrs={
                    "long_name": "Lead time",
                    "standard_name": "forecast_period",
                },
            ),
            "latitude": xr.Variable(
                ("latitude",),
                lat,
                attrs={
                    "long_name": "Latitude",
                    "standard_name": "latitude",
                    "units": "degrees_north",
                    "axis": "Y",
                },
            ),
            "longitude": xr.Variable(
                ("longitude",),
                lon,
                attrs={
                    "long_name": "Longitude",
                    "standard_name": "longitude",
                    "units": "degrees_east",
                    "axis": "X",
                },
            ),
        }

    def derive_coordinates(self) -> dict[str, xr.Variable]:
        """Define derived coordinates."""
        # Note: In actual implementation, valid_time would be calculated as
        # init_time + lead_time, but for the template we'll skip this
        # as it requires actual data
        return {}

    def data_vars(self) -> dict[str, tuple[tuple[str, ...], Any]]:
        """Define data variables with their dimensions and fill values.

        Matches the 9 essential parameters from ECMWF Open Data.
        """
        dims = ("init_time", "lead_time", "latitude", "longitude")

        return {
            # Temperature and humidity
            "temperature_2m": (dims, np.nan),
            "dewpoint_2m": (dims, np.nan),
            # Wind
            "wind_u_10m": (dims, np.nan),
            "wind_v_10m": (dims, np.nan),
            # Pressure
            "mean_sea_level_pressure": (dims, np.nan),
            "surface_pressure": (dims, np.nan),
            # Precipitation
            "total_precipitation": (dims, 0.0),
            # Atmospheric water
            "total_column_water_vapour": (dims, np.nan),
            # Radiation
            "surface_solar_radiation_downwards": (dims, np.nan),
        }

    def encoding(self) -> dict[str, dict[str, Any]]:
        """Return encoding with Blosc compression and chunking."""
        compressor = Blosc(cname="zstd", clevel=3, shuffle=Blosc.SHUFFLE)

        encoding = {}

        # Coordinates
        for coord_name in self.coords().keys():
            encoding[coord_name] = {"compressor": compressor}

        # Data variables with chunking
        chunks = {
            "init_time": 1,
            "lead_time": 24,  # ~3 days of 3-hourly data
            "latitude": 360,  # 90 degrees worth
            "longitude": 720,  # 180 degrees worth
        }

        for var_name in self.data_vars().keys():
            encoding[var_name] = {
                "compressor": compressor,
                "chunks": [
                    chunks["init_time"],
                    chunks["lead_time"],
                    chunks["latitude"],
                    chunks["longitude"],
                ],
            }

        return encoding

    def chunks(self) -> dict[str, Any]:
        """Return chunking configuration for dask."""
        return {
            "init_time": 1,
            "lead_time": 24,
            "latitude": 360,
            "longitude": 720,
        }

    def attrs(self) -> dict[str, Any]:
        """Return global attributes."""
        return {
            "title": "ECMWF IFS High-Resolution 15-day Forecast",
            "institution": "European Centre for Medium-Range Weather Forecasts",
            "source": "ECMWF Integrated Forecasting System (IFS)",
            "conventions": "CF-1.8",
            "resolution": "0.25 degrees",
            "forecast_horizon": "15 days (360 hours)",
            "temporal_resolution": "3-hourly (0-144h), 6-hourly (150-360h)",
            "coverage": "Global",
            "license": "CC-BY-4.0",
            "references": "https://www.ecmwf.int/en/forecasts/datasets/open-data",
        }
