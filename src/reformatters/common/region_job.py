"""Base class for processing data in regional chunks."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import xarray as xr


@dataclass
class SourceFileCoord:
    """Coordinates identifying a source file to download."""

    init_time: datetime
    lead_time_hours: int | None = None


class RegionJob(ABC):
    """Base class for downloading, processing, and writing data.

    This class orchestrates the workflow of:
    1. Identifying source files to download
    2. Downloading files (with caching)
    3. Reading and transforming data
    4. Writing to zarr store

    Regional processing allows parallelization across different init times,
    lead times, or geographic regions.
    """

    def __init__(self, zarr_store: Path, cache_dir: Path | None = None):
        """Initialize region job.

        Args:
            zarr_store: Path to output zarr store
            cache_dir: Optional directory for caching downloaded files
        """
        self.zarr_store = zarr_store
        self.cache_dir = cache_dir or Path(".cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def generate_source_file_coords(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> list[SourceFileCoord]:
        """Generate list of source files to download.

        Args:
            start_time: Start of time range (None = latest available)
            end_time: End of time range (None = latest available)

        Returns:
            List of source file coordinates
        """
        pass

    @abstractmethod
    def download_file(self, coord: SourceFileCoord) -> Path:
        """Download source file and return path to cached file.

        Args:
            coord: Source file coordinates

        Returns:
            Path to downloaded file
        """
        pass

    @abstractmethod
    def read_data(self, file_path: Path, coord: SourceFileCoord) -> xr.Dataset:
        """Read data from source file and return as xarray Dataset.

        Args:
            file_path: Path to source file
            coord: Source file coordinates

        Returns:
            Dataset with data from source file
        """
        pass

    def transform_data(self, ds: xr.Dataset, coord: SourceFileCoord) -> xr.Dataset:
        """Transform data before writing (optional).

        Default implementation returns data unchanged. Override to add
        transformations like unit conversions, deaccumulation, etc.

        Args:
            ds: Input dataset
            coord: Source file coordinates

        Returns:
            Transformed dataset
        """
        return ds

    def write_data(self, ds: xr.Dataset, coord: SourceFileCoord) -> None:
        """Write data to zarr store.

        Args:
            ds: Dataset to write
            coord: Source file coordinates
        """
        # Determine region to write based on init_time
        region = {"init_time": slice(coord.init_time, coord.init_time)}

        try:
            ds.to_zarr(self.zarr_store, mode="r+", region=region, consolidated=False)
        except Exception as e:
            print(f"Error writing data for {coord.init_time}: {e}")
            raise

    def process_coord(self, coord: SourceFileCoord) -> None:
        """Process a single source file coordinate.

        This orchestrates: download → read → transform → write

        Args:
            coord: Source file coordinate to process
        """
        print(f"Processing {coord.init_time}")

        try:
            # Download
            file_path = self.download_file(coord)

            # Read
            ds = self.read_data(file_path, coord)

            # Transform
            ds = self.transform_data(ds, coord)

            # Write
            self.write_data(ds, coord)

            print(f"✓ Completed {coord.init_time}")

        except Exception as e:
            print(f"✗ Failed {coord.init_time}: {e}")
            raise

    def run(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> None:
        """Run the complete job for specified time range.

        Args:
            start_time: Start of time range (None = latest)
            end_time: End of time range (None = latest)
        """
        coords = self.generate_source_file_coords(start_time, end_time)

        print(f"Processing {len(coords)} source files")

        for coord in coords:
            self.process_coord(coord)

        print("Job complete")
