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
    # Using only parameters definitely available in ECMWF Open Data
    PARAMETERS = [
        "2t",  # 2m temperature
        "10u",  # 10m u-wind
        "10v",  # 10m v-wind
        "tp",  # total precipitation
        "sp",  # surface pressure
        "msl",  # mean sea level pressure
        "tcc",  # total cloud cover
        "2d",  # 2m dewpoint temperature (proxy for humidity)
    ]

    # Map GRIB parameter names to our variable names
    PARAM_MAP = {
        "2t": "temperature_2m",
        "10u": "wind_u_10m",
        "10v": "wind_v_10m",
        "tp": "total_precipitation",
        "sp": "surface_pressure",
        "msl": "mean_sea_level_pressure",
        "tcc": "total_cloud_cover",
        "2d": "relative_humidity_2m",  # Will compute from dewpoint if needed
    }

    def __init__(self, zarr_store: Path, cache_dir: Path | None = None):
        """Initialize ECMWF region job."""
        super().__init__(zarr_store, cache_dir)
        self.client = Client(source="ecmwf")

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
        run_hours = [0, 6, 12, 18]

        if start_time is None and end_time is None:
            # Operational mode: get latest run only
            # The latest run is typically available 1 hour after run time
            now = datetime.utcnow()
            latest_run_hour = max([h for h in run_hours if h <= now.hour], default=run_hours[-1])

            if latest_run_hour > now.hour:
                # Use previous day's last run
                latest_run = now.replace(hour=run_hours[-1], minute=0, second=0, microsecond=0)
                latest_run -= timedelta(days=1)
            else:
                latest_run = now.replace(
                    hour=latest_run_hour, minute=0, second=0, microsecond=0
                )

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

        try:
            # Download all parameters and lead times
            # Note: ECMWF API downloads all lead times by default for a given run
            # Download each parameter separately to avoid conflicts
            temp_files = []
            for param in self.PARAMETERS:
                param_file = self.cache_dir / f"ecmwf_ifs_{coord.init_time.strftime('%Y%m%d_%H%M')}_{param}.grib2"

                if not param_file.exists():
                    print(f"  Downloading {param}...")
                    try:
                        self.client.retrieve(
                            date=coord.init_time.strftime("%Y-%m-%d"),
                            time=coord.init_time.hour,
                            type="fc",  # forecast
                            param=[param],
                            target=str(param_file),
                        )
                        temp_files.append(param_file)
                    except Exception as e:
                        print(f"  Warning: Could not download {param}: {e}")
                        continue
                else:
                    temp_files.append(param_file)

            if not temp_files:
                raise ValueError("No parameters could be downloaded")

            # For now, return the first file (we'll handle multiple files later)
            # In a production system, you'd merge these GRIB files
            print(f"  Downloaded {len(temp_files)} parameter files")
            return temp_files[0] if temp_files else cache_file

        except Exception as e:
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
        print(f"  Reading GRIB2 file: {file_path}")

        try:
            import cfgrib

            # Read GRIB file using cfgrib
            # Open all messages (multiple parameters and lead times)
            datasets = []

            for param in self.PARAMETERS:
                try:
                    ds = cfgrib.open_datasets(
                        str(file_path),
                        backend_kwargs={
                            "filter_by_keys": {"shortName": param},
                            "indexpath": "",
                        },
                    )

                    # cfgrib may return multiple datasets for different levels
                    # We want surface level data
                    for d in ds:
                        if param in self.PARAM_MAP:
                            datasets.append(d)
                            break

                except Exception as e:
                    print(f"  Warning: Could not read {param}: {e}")

            # Merge datasets
            if not datasets:
                raise ValueError("No data could be read from GRIB file")

            ds = xr.merge(datasets)

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

        # Ensure init_time is a coordinate
        if "init_time" not in ds.coords:
            ds = ds.expand_dims(init_time=[pd.Timestamp(coord.init_time)])

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

        # Select only variables we want
        wanted_vars = list(self.PARAM_MAP.values())
        available_vars = [v for v in wanted_vars if v in ds.data_vars]
        ds = ds[available_vars]

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
