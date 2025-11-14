"""Region job for ECMWF IFS 15-day forecast."""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from ecmwf.opendata import Client

from reformatters.common.region_job import RegionJob, SourceFileCoord


class EcmwfIfsForecast15DayRegionJob(RegionJob):
    """Process ECMWF IFS 15-day forecast data.

    Downloads GRIB2 files from ECMWF Open Data and converts to zarr format.
    """

    # ECMWF parameter short names (GRIB parameter codes)
    # Using only parameters available in ECMWF Open Data
    PARAMETERS = [
        "2t",  # 2m temperature
        "10u",  # 10m u-wind
        "10v",  # 10m v-wind
        "tp",  # total precipitation
        "sp",  # surface pressure
        "msl",  # mean sea level pressure
        "2d",  # 2m dewpoint temperature (for humidity calculation)
    ]

    # Map GRIB parameter names to our variable names
    PARAM_MAP = {
        "2t": "temperature_2m",
        "10u": "wind_u_10m",
        "10v": "wind_v_10m",
        "tp": "total_precipitation",
        "sp": "surface_pressure",
        "msl": "mean_sea_level_pressure",
        "2d": "relative_humidity_2m",  # Will compute from dewpoint if needed
    }

    def __init__(self, zarr_store: Path, cache_dir: Path | None = None):
        """Initialize ECMWF region job."""
        super().__init__(zarr_store, cache_dir)
        self.client = Client(source="ecmwf")

        # Generate forecast step list for ECMWF Open Data (00/12 UTC runs)
        # 0-144h every 3 hours, then 150-240h every 6 hours
        self.forecast_steps = list(range(0, 145, 3)) + list(range(150, 241, 6))

    def generate_source_file_coords(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> list[SourceFileCoord]:
        """Generate list of ECMWF forecast runs to download.

        Args:
            start_time: Start time (None = latest only)
            end_time: End time (None = latest only)

        Returns:
            List of source file coordinates
        """
        # ECMWF runs at 00, 06, 12, 18 UTC
        # But only 00/12 UTC runs have long-range forecasts (0-240h)
        # 06/18 UTC runs only have 0-90h
        run_hours = [0, 12]

        if start_time is None and end_time is None:
            # Operational mode: get latest AVAILABLE run
            # ECMWF Open Data has 7-11 hour delay after forecast time
            # So we need to go back at least 12 hours to be safe
            now = datetime.utcnow()
            available_time = now - timedelta(hours=12)

            # Find the most recent run hour before available_time
            latest_run_hour = max([h for h in run_hours if h <= available_time.hour], default=run_hours[-1])

            if latest_run_hour > available_time.hour:
                # Use previous day's last run
                latest_run = available_time.replace(hour=run_hours[-1], minute=0, second=0, microsecond=0)
                latest_run -= timedelta(days=1)
            else:
                latest_run = available_time.replace(
                    hour=latest_run_hour, minute=0, second=0, microsecond=0
                )

            print(f"Requesting forecast from {latest_run} (accounting for ~8-11 hour data delay)")
            return [SourceFileCoord(init_time=latest_run)]

        else:
            # Backfill mode: generate all runs in range
            coords = []
            current = start_time or datetime(2024, 1, 1)
            end = end_time or datetime.utcnow()

            while current <= end:
                for hour in run_hours:
                    run_time = current.replace(hour=hour, minute=0, second=0, microsecond=0)
                    if start_time <= run_time <= end:
                        coords.append(SourceFileCoord(init_time=run_time))
                current += timedelta(days=1)

            return coords

    def download_file(self, coord: SourceFileCoord) -> Path:
        """Download GRIB2 file from ECMWF.

        Args:
            coord: Source file coordinate

        Returns:
            Path to downloaded GRIB2 file
        """
        # Create cache file path
        cache_file = (
            self.cache_dir
            / f"ecmwf_ifs_{coord.init_time.strftime('%Y%m%d_%H%M')}.grib2"
        )

        if cache_file.exists():
            print(f"  Using cached file: {cache_file}")
            return cache_file

        print(f"  Downloading forecast from {coord.init_time}")
        print(f"  Parameters: {', '.join(self.PARAMETERS)}")
        print(f"  Forecast steps: {len(self.forecast_steps)} steps (0-240h)")

        try:
            # Try to download specific date/time first
            self.client.retrieve(
                date=coord.init_time.strftime("%Y-%m-%d"),
                time=coord.init_time.hour,
                type="fc",  # forecast
                param=self.PARAMETERS,  # All parameters at once
                step=self.forecast_steps,  # All forecast lead times
                target=str(cache_file),
            )

            print(f"  Downloaded: {cache_file.name} ({cache_file.stat().st_size / 1024 / 1024:.1f} MB)")
            return cache_file

        except Exception as e:
            # If specific date fails (404), try getting latest available
            if "404" in str(e):
                print(f"  Requested forecast not yet available (404 error)")
                print(f"  Attempting to download latest available forecast instead...")

                try:
                    # Use client's automatic latest detection (don't specify date/time)
                    result = self.client.retrieve(
                        type="fc",
                        param=self.PARAMETERS,
                        step=self.forecast_steps,  # All forecast lead times
                        target=str(cache_file),
                    )

                    # Rename file to match actual datetime
                    actual_time = result.datetime
                    actual_cache_file = (
                        self.cache_dir
                        / f"ecmwf_ifs_{actual_time.strftime('%Y%m%d_%H%M')}.grib2"
                    )
                    cache_file.rename(actual_cache_file)

                    print(f"  Downloaded latest available: {actual_time}")
                    print(f"  File: {actual_cache_file.name} ({actual_cache_file.stat().st_size / 1024 / 1024:.1f} MB)")

                    # Update coord to reflect actual time
                    coord.init_time = actual_time

                    return actual_cache_file

                except Exception as e2:
                    print(f"  Error downloading latest: {e2}")
                    raise
            else:
                print(f"  Error downloading: {e}")
                raise

    def read_data(self, file_path: Path, coord: SourceFileCoord) -> xr.Dataset:
        """Read GRIB2 file and convert to xarray Dataset.

        Args:
            file_path: Path to GRIB2 file
            coord: Source file coordinate

        Returns:
            xarray Dataset with standardized coordinates
        """
        print(f"  Reading GRIB2 file: {file_path.name}")

        try:
            import cfgrib

            # Open all datasets from the multi-parameter GRIB file
            # cfgrib will split into multiple datasets based on type/level
            ds_list = cfgrib.open_datasets(
                str(file_path),
                backend_kwargs={
                    "indexpath": "",
                },
            )

            print(f"  Found {len(ds_list)} dataset(s) in GRIB file")

            # Merge all datasets
            if not ds_list:
                raise ValueError("No data could be read from GRIB file")

            # Drop height coordinates that conflict between datasets
            # (10m for wind, 2m for temperature, etc - already encoded in variable names)
            cleaned_datasets = []
            for ds_part in ds_list:
                # Drop conflicting height-related coordinates
                coords_to_drop = [c for c in ['heightAboveGround', 'level', 'isobaricInhPa']
                                 if c in ds_part.coords]
                if coords_to_drop:
                    ds_part = ds_part.drop_vars(coords_to_drop)
                cleaned_datasets.append(ds_part)

            # Merge with compat='override' to handle any remaining conflicts
            ds = xr.merge(cleaned_datasets, compat='override')

            # Standardize coordinates and variable names
            ds = self._standardize_dataset(ds, coord)

            print(f"  Read {len(ds.data_vars)} variables")
            return ds

        except Exception as e:
            print(f"  Error reading GRIB file: {e}")
            raise

    def _standardize_dataset(self, ds: xr.Dataset, coord: SourceFileCoord) -> xr.Dataset:
        """Standardize dataset coordinates and variable names.

        Args:
            ds: Input dataset from GRIB
            coord: Source file coordinate

        Returns:
            Standardized dataset
        """
        # Rename coordinates to match our template
        coord_renames = {}
        if "latitude" not in ds.coords and "lat" in ds.coords:
            coord_renames["lat"] = "latitude"
        if "longitude" not in ds.coords and "lon" in ds.coords:
            coord_renames["lon"] = "longitude"
        if "step" in ds.coords:  # lead time
            coord_renames["step"] = "lead_time"
        if "time" in ds.coords:  # init time
            coord_renames["time"] = "init_time"

        if coord_renames:
            ds = ds.rename(coord_renames)

        # Rename variables
        var_renames = {}
        for grib_param, our_name in self.PARAM_MAP.items():
            # cfgrib uses GRIB short names
            if grib_param in ds:
                var_renames[grib_param] = our_name
            # Sometimes cfgrib adds suffixes
            for var in ds.data_vars:
                if var.startswith(grib_param) and var not in var_renames:
                    var_renames[var] = our_name

        if var_renames:
            ds = ds.rename(var_renames)

        # Select only variables we want (do this early before coordinate processing)
        wanted_vars = list(self.PARAM_MAP.values())
        available_vars = [v for v in wanted_vars if v in ds.data_vars]
        ds = ds[available_vars]

        # Ensure init_time is a coordinate (after variable selection)
        if "init_time" not in ds.coords:
            ds = ds.expand_dims(init_time=[pd.Timestamp(coord.init_time)])

        # Make sure init_time is indexed
        if "init_time" in ds.dims and "init_time" not in ds.indexes:
            ds = ds.set_coords("init_time")

        # Convert lead_time to timedelta if needed
        if "lead_time" in ds.coords and not np.issubdtype(
            ds.lead_time.dtype, np.timedelta64
        ):
            ds["lead_time"] = pd.to_timedelta(ds.lead_time.values, unit="h")

        # Ensure latitude is descending (90 to -90)
        if "latitude" in ds.coords and ds.latitude[0] < ds.latitude[-1]:
            ds = ds.isel(latitude=slice(None, None, -1))

        # Ensure longitude is 0-360
        if "longitude" in ds.coords:
            lon = ds.longitude.values
            if lon.min() < 0:
                ds = ds.assign_coords(longitude=(ds.longitude % 360))
                ds = ds.sortby("longitude")

        return ds

    def transform_data(self, ds: xr.Dataset, coord: SourceFileCoord) -> xr.Dataset:
        """Transform data before writing.

        Handles unit conversions, deaccumulation, etc.

        Args:
            ds: Input dataset
            coord: Source file coordinate

        Returns:
            Transformed dataset
        """
        # Total precipitation is accumulated, may need deaccumulation
        # depending on GRIB encoding
        if "total_precipitation" in ds:
            # ECMWF precipitation is typically accumulated from start
            # For now, keep as-is (user can deaccumulate if needed)
            pass

        # Ensure all data is float32 for storage efficiency
        for var in ds.data_vars:
            if ds[var].dtype != np.float32:
                ds[var] = ds[var].astype(np.float32)

        return ds
