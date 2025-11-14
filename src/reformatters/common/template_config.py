"""Base class for defining dataset templates."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import xarray as xr
import zarr


class TemplateConfig(ABC):
    """Base class for defining zarr dataset structure and metadata.

    This class defines the complete structure of a dataset including dimensions,
    coordinates, data variables, and their encoding. It generates a template
    zarr dataset that can be used for writing actual data.

    Subclasses should implement:
    - dimension_coordinates(): Define dimensional coordinates (e.g., time, lat, lon)
    - derive_coordinates(): Define derived/non-dimensional coordinates
    - data_vars(): Define data variables and their properties
    """

    @abstractmethod
    def dimension_coordinates(self) -> dict[str, xr.Variable]:
        """Return dimensional coordinates (e.g., init_time, lead_time, lat, lon)."""
        pass

    def derive_coordinates(self) -> dict[str, xr.Variable]:
        """Return derived coordinates (e.g., valid_time = init_time + lead_time).

        Default implementation returns empty dict. Override to add derived coordinates.
        """
        return {}

    @abstractmethod
    def data_vars(self) -> dict[str, tuple[tuple[str, ...], Any]]:
        """Return data variables as {name: (dimensions, fill_value)}.

        Example:
            {
                "temperature_2m": (("init_time", "lead_time", "latitude", "longitude"), np.nan),
                "precipitation": (("init_time", "lead_time", "latitude", "longitude"), 0.0),
            }
        """
        pass

    def coords(self) -> dict[str, xr.Variable]:
        """Return all coordinates (dimensional + derived)."""
        return {**self.dimension_coordinates(), **self.derive_coordinates()}

    def encoding(self) -> dict[str, dict[str, Any]]:
        """Return encoding configuration for variables.

        Default uses Blosc compression. Override to customize.
        """
        from numcodecs import Blosc

        compressor = Blosc(cname="zstd", clevel=3, shuffle=Blosc.SHUFFLE)

        encoding = {}
        for var_name in self.coords().keys():
            encoding[var_name] = {"compressor": compressor}

        for var_name in self.data_vars().keys():
            encoding[var_name] = {"compressor": compressor}

        return encoding

    def chunks(self) -> dict[str, Any]:
        """Return chunking configuration.

        Default returns empty dict (no chunking). Override to customize.
        """
        return {}

    def attrs(self) -> dict[str, Any]:
        """Return global attributes for the dataset."""
        return {
            "title": "ECMWF Open Data",
            "institution": "ECMWF",
            "source": "ECMWF Integrated Forecasting System",
            "conventions": "CF-1.8",
        }

    def generate_template(self) -> xr.Dataset:
        """Generate template xarray Dataset with metadata but no data."""
        coords = self.coords()
        data_vars_dict = {}

        for var_name, (dims, fill_value) in self.data_vars().items():
            shape = tuple(len(coords[dim]) for dim in dims)
            data_vars_dict[var_name] = (dims, xr.Variable(dims, data=None).data)

        ds = xr.Dataset(data_vars=data_vars_dict, coords=coords, attrs=self.attrs())

        # Apply encoding
        encoding = self.encoding()
        for var_name, enc in encoding.items():
            if var_name in ds:
                ds[var_name].encoding.update(enc)

        # Apply chunking
        chunks = self.chunks()
        if chunks:
            ds = ds.chunk(chunks)

        return ds

    def write_template(self, path: Path) -> None:
        """Write template dataset to zarr store."""
        ds = self.generate_template()
        path.parent.mkdir(parents=True, exist_ok=True)

        # Clear existing store if it exists
        if path.exists():
            import shutil

            shutil.rmtree(path)

        ds.to_zarr(path, mode="w", consolidated=True)
        print(f"Template written to {path}")
