"""Base class for dataset orchestration."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import xarray as xr

from reformatters.common.region_job import RegionJob
from reformatters.common.template_config import TemplateConfig


class Dataset(ABC):
    """Base class for orchestrating dataset creation and updates.

    This class coordinates the TemplateConfig and RegionJob to manage
    the complete lifecycle of a dataset:
    - Creating initial template
    - Running operational updates
    - Backfilling historical data
    - Validating dataset
    """

    def __init__(self, storage_path: Path):
        """Initialize dataset.

        Args:
            storage_path: Path to zarr storage location
        """
        self.storage_path = storage_path

    @abstractmethod
    def template_config(self) -> TemplateConfig:
        """Return the template configuration for this dataset."""
        pass

    @abstractmethod
    def region_job(self) -> RegionJob:
        """Return the region job for processing data."""
        pass

    @property
    def zarr_store(self) -> Path:
        """Path to the zarr store."""
        return self.storage_path / "latest.zarr"

    def update_template(self) -> None:
        """Update the zarr template."""
        print("Updating template...")
        config = self.template_config()
        config.write_template(self.zarr_store)
        print("Template updated successfully")

    def update(self) -> None:
        """Run operational update (latest data only)."""
        print("Running operational update...")

        # Ensure template exists
        if not self.zarr_store.exists():
            print("Template not found, creating...")
            self.update_template()

        # Process latest data
        job = self.region_job()
        job.run(start_time=None, end_time=None)  # None = latest

        # Consolidate metadata
        self._consolidate_metadata()

        print("Operational update complete")

    def backfill(self, end_date: datetime, start_date: datetime | None = None) -> None:
        """Backfill historical data.

        Args:
            end_date: End date for backfill
            start_date: Start date for backfill (None = from beginning)
        """
        print(f"Running backfill from {start_date} to {end_date}...")

        # Ensure template exists
        if not self.zarr_store.exists():
            print("Template not found, creating...")
            self.update_template()

        # Process historical data
        job = self.region_job()
        job.run(start_time=start_date, end_time=end_date)

        # Consolidate metadata
        self._consolidate_metadata()

        print("Backfill complete")

    def validate(self) -> bool:
        """Validate the dataset.

        Returns:
            True if validation passes, False otherwise
        """
        print("Validating dataset...")

        if not self.zarr_store.exists():
            print("✗ Validation failed: Zarr store does not exist")
            return False

        try:
            # Open dataset
            ds = xr.open_zarr(self.zarr_store)

            # Check for data
            if len(ds.dims) == 0:
                print("✗ Validation failed: Dataset has no dimensions")
                return False

            # Check for recent data
            if "init_time" in ds.dims:
                latest_time = ds.init_time.max().values
                print(f"Latest init_time: {latest_time}")

                # Check if data is recent (within last 24 hours)
                import pandas as pd

                now = pd.Timestamp.now(tz="UTC")
                latest_time_ts = pd.Timestamp(latest_time)

                age_hours = (now - latest_time_ts).total_seconds() / 3600
                if age_hours > 24:
                    print(f"⚠ Warning: Latest data is {age_hours:.1f} hours old")
                else:
                    print(f"✓ Data is recent ({age_hours:.1f} hours old)")

            # Check for NaN values
            for var in ds.data_vars:
                nan_count = ds[var].isnull().sum().values
                total_count = ds[var].size
                nan_pct = (nan_count / total_count) * 100 if total_count > 0 else 0

                if nan_pct > 50:
                    print(f"⚠ Warning: {var} has {nan_pct:.1f}% NaN values")
                else:
                    print(f"✓ {var}: {nan_pct:.2f}% NaN")

            print("✓ Validation passed")
            return True

        except Exception as e:
            print(f"✗ Validation failed: {e}")
            return False

    def _consolidate_metadata(self) -> None:
        """Consolidate zarr metadata for efficient access."""
        try:
            import zarr

            store = zarr.open_group(self.zarr_store, mode="r+")
            zarr.consolidate_metadata(self.zarr_store)
            print("✓ Metadata consolidated")
        except Exception as e:
            print(f"⚠ Warning: Could not consolidate metadata: {e}")
