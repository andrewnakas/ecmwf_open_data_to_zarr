"""Generate preview visualizations from latest forecast data."""

import json
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

# Use non-interactive backend
matplotlib.use("Agg")

# Try to import cartopy, but fallback if not available
try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    HAS_CARTOPY = True
except ImportError:
    HAS_CARTOPY = False
    print("Warning: cartopy not available, using basic plots")


def generate_previews(zarr_path: Path, output_dir: Path) -> dict:
    """Generate preview images and metadata from latest forecast.

    Args:
        zarr_path: Path to zarr store
        output_dir: Directory to save preview images

    Returns:
        Dictionary with metadata about the latest forecast
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading dataset from {zarr_path}")
    ds = xr.open_zarr(zarr_path, decode_timedelta=True)

    # Get latest forecast
    latest_init = ds.init_time.max().values
    latest_ds = ds.sel(init_time=latest_init)

    print(f"Latest forecast: {latest_init}")

    # Generate metadata
    metadata = {
        "init_time": str(pd.Timestamp(latest_init)),
        "init_time_utc": pd.Timestamp(latest_init).strftime("%Y-%m-%d %H:%M UTC"),
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "variables": list(ds.data_vars.keys()),
        "dimensions": {dim: int(size) for dim, size in ds.dims.items()},
        "forecast_hours": int(ds.lead_time.max().values / np.timedelta64(1, "h")),
    }

    # Generate temperature map at 24h
    print("Generating temperature map...")
    generate_temperature_map(latest_ds, output_dir, metadata)

    # Generate wind map at 24h
    print("Generating wind map...")
    generate_wind_map(latest_ds, output_dir, metadata)

    # Generate precipitation map
    print("Generating precipitation map...")
    generate_precipitation_map(latest_ds, output_dir, metadata)

    # Generate time series for major cities
    print("Generating city forecasts...")
    generate_city_forecasts(latest_ds, output_dir, metadata)

    # Save metadata
    metadata_path = output_dir / "latest_forecast.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved metadata to {metadata_path}")

    return metadata


def generate_temperature_map(ds: xr.Dataset, output_dir: Path, metadata: dict) -> None:
    """Generate global temperature map at 24h lead time."""
    temp_24h = ds["temperature_2m"].sel(lead_time="24h") - 273.15  # Convert to Celsius

    if HAS_CARTOPY:
        fig, ax = plt.subplots(
            figsize=(16, 10), subplot_kw={"projection": ccrs.PlateCarree()}
        )

        im = temp_24h.plot(
            ax=ax,
            transform=ccrs.PlateCarree(),
            cmap="RdYlBu_r",
            vmin=-30,
            vmax=40,
            cbar_kwargs={"label": "Temperature (°C)", "shrink": 0.8},
            add_colorbar=True,
        )

        ax.coastlines(linewidth=0.5)
        ax.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.5, alpha=0.5)
        ax.gridlines(draw_labels=True, alpha=0.3, linewidth=0.5)

        ax.set_title(
            f"Global Temperature Forecast (+24h)\n{metadata['init_time_utc']}",
            fontsize=16,
            fontweight="bold",
        )
    else:
        fig, ax = plt.subplots(figsize=(16, 10))
        temp_24h.plot(
            ax=ax, cmap="RdYlBu_r", vmin=-30, vmax=40, cbar_kwargs={"label": "Temperature (°C)"}
        )
        ax.set_title(
            f"Global Temperature Forecast (+24h)\n{metadata['init_time_utc']}",
            fontsize=16,
            fontweight="bold",
        )

    plt.tight_layout()
    output_path = output_dir / "temperature_24h.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"Saved: {output_path}")


def generate_wind_map(ds: xr.Dataset, output_dir: Path, metadata: dict) -> None:
    """Generate global wind speed map at 24h lead time."""
    u_wind = ds["wind_u_10m"].sel(lead_time="24h")
    v_wind = ds["wind_v_10m"].sel(lead_time="24h")
    wind_speed = np.sqrt(u_wind**2 + v_wind**2)

    if HAS_CARTOPY:
        fig, ax = plt.subplots(
            figsize=(16, 10), subplot_kw={"projection": ccrs.PlateCarree()}
        )

        im = wind_speed.plot(
            ax=ax,
            transform=ccrs.PlateCarree(),
            cmap="YlOrRd",
            vmin=0,
            vmax=25,
            cbar_kwargs={"label": "Wind Speed (m/s)", "shrink": 0.8},
            add_colorbar=True,
        )

        ax.coastlines(linewidth=0.5)
        ax.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.5, alpha=0.5)
        ax.gridlines(draw_labels=True, alpha=0.3, linewidth=0.5)

        ax.set_title(
            f"Global Wind Speed Forecast (+24h)\n{metadata['init_time_utc']}",
            fontsize=16,
            fontweight="bold",
        )
    else:
        fig, ax = plt.subplots(figsize=(16, 10))
        wind_speed.plot(
            ax=ax, cmap="YlOrRd", vmin=0, vmax=25, cbar_kwargs={"label": "Wind Speed (m/s)"}
        )
        ax.set_title(
            f"Global Wind Speed Forecast (+24h)\n{metadata['init_time_utc']}",
            fontsize=16,
            fontweight="bold",
        )

    plt.tight_layout()
    output_path = output_dir / "wind_speed_24h.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"Saved: {output_path}")


def generate_precipitation_map(ds: xr.Dataset, output_dir: Path, metadata: dict) -> None:
    """Generate precipitation map at 24h lead time."""
    precip_24h = ds["total_precipitation"].sel(lead_time="24h") * 1000  # Convert m to mm

    if HAS_CARTOPY:
        fig, ax = plt.subplots(
            figsize=(16, 10), subplot_kw={"projection": ccrs.PlateCarree()}
        )

        im = precip_24h.plot(
            ax=ax,
            transform=ccrs.PlateCarree(),
            cmap="Blues",
            vmin=0,
            vmax=50,
            cbar_kwargs={"label": "Precipitation (mm)", "shrink": 0.8},
            add_colorbar=True,
        )

        ax.coastlines(linewidth=0.5)
        ax.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.5, alpha=0.5)
        ax.gridlines(draw_labels=True, alpha=0.3, linewidth=0.5)

        ax.set_title(
            f"Total Precipitation Forecast (+24h)\n{metadata['init_time_utc']}",
            fontsize=16,
            fontweight="bold",
        )
    else:
        fig, ax = plt.subplots(figsize=(16, 10))
        precip_24h.plot(
            ax=ax, cmap="Blues", vmin=0, vmax=50, cbar_kwargs={"label": "Precipitation (mm)"}
        )
        ax.set_title(
            f"Total Precipitation Forecast (+24h)\n{metadata['init_time_utc']}",
            fontsize=16,
            fontweight="bold",
        )

    plt.tight_layout()
    output_path = output_dir / "precipitation_24h.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"Saved: {output_path}")


def generate_city_forecasts(ds: xr.Dataset, output_dir: Path, metadata: dict) -> None:
    """Generate temperature forecasts for major cities."""
    cities = {
        "New York": (40.7, 286.0),  # -74°W = 286°E
        "London": (51.5, 359.9),  # -0.1°W = 359.9°E
        "Tokyo": (35.7, 139.7),
        "Sydney": (-33.9, 151.2),
        "São Paulo": (-23.5, 313.4),  # -46.6°W = 313.4°E
        "Mumbai": (19.1, 72.9),
    }

    fig, ax = plt.subplots(figsize=(14, 8))

    for city_name, (lat, lon) in cities.items():
        city_data = ds.sel(latitude=lat, longitude=lon, method="nearest")
        temp_c = city_data["temperature_2m"] - 273.15

        # Convert lead_time to hours for plotting
        hours = city_data.lead_time.values / np.timedelta64(1, "h")
        ax.plot(hours, temp_c.values, label=city_name, linewidth=2, marker="o", markersize=3)

    ax.set_xlabel("Forecast Lead Time (hours)", fontsize=12)
    ax.set_ylabel("Temperature (°C)", fontsize=12)
    ax.set_title(
        f"Temperature Forecast for Major Cities\n{metadata['init_time_utc']}",
        fontsize=14,
        fontweight="bold",
    )
    ax.legend(loc="best", fontsize=10)
    ax.grid(True, alpha=0.3, linestyle="--")

    plt.tight_layout()
    output_path = output_dir / "city_forecasts.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"Saved: {output_path}")

    # Save city data to metadata
    city_temps = {}
    for city_name, (lat, lon) in cities.items():
        city_data = ds.sel(latitude=lat, longitude=lon, method="nearest")
        temp_24h = float(city_data["temperature_2m"].sel(lead_time="24h").values - 273.15)
        city_temps[city_name] = round(temp_24h, 1)

    metadata["city_temperatures_24h"] = city_temps


if __name__ == "__main__":
    import sys

    zarr_path = Path("data/ecmwf/ifs/forecast-15-day/latest.zarr")
    output_dir = Path("docs/previews")

    if len(sys.argv) > 1:
        zarr_path = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_dir = Path(sys.argv[2])

    print(f"Generating previews from {zarr_path} to {output_dir}")
    metadata = generate_previews(zarr_path, output_dir)

    print("\nMetadata:")
    print(json.dumps(metadata, indent=2))
    print("\n✓ Preview generation complete!")
