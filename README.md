# ECMWF IFS High-Resolution Forecast

**Status: Updating** • 4 times daily • Real-time global weather forecasts

## Dataset Overview

High-resolution global weather forecasts from the European Centre for Medium-Range Weather Forecasts (ECMWF) Integrated Forecasting System (IFS), updated four times daily at forecast initialization times 00, 06, 12, and 18 UTC.

**Spatial Domain:** Global
**Spatial Resolution:** 0.25° (~25 km)
**Spatial Coverage:** 90°N to 90°S, 0°E to 360°E

**Forecast Initialization:** 00, 06, 12, 18 UTC
**Forecast Range:**
- 00z and 12z runs: 0-240 hours (10 days)
- 06z and 18z runs: 0-90 hours (3.75 days)

**Forecast Resolution:**
- 0-144h: 3-hourly
- 150-240h: 6-hourly (00z/12z runs only)

## Description

The ECMWF IFS is a comprehensive Earth-system model producing global numerical weather predictions. This dataset provides real-time access to ECMWF's high-resolution deterministic forecasts through their Open Data initiative, made freely available under the Creative Commons CC-BY-4.0 license.

Forecasts are initialized four times daily. The 00 and 12 UTC runs provide extended 10-day outlooks with 240-hour forecast horizons, while the 06 and 18 UTC runs offer more frequent updates with 90-hour forecasts optimized for short-range applications.

Data is automatically fetched from ECMWF's dissemination system approximately 8-11 hours after model initialization, processed into cloud-optimized Zarr format, and published via GitHub Pages with rolling 48-hour retention.

## Code Examples

### Access Latest Forecast

```python
import xarray as xr

# Open latest forecast
ds = xr.open_zarr(
    "https://<username>.github.io/ecmwf_open_data_to_zarr/data/ecmwf/ifs/forecast-15-day/latest.zarr",
    consolidated=True
)

# View dataset structure
print(ds)
```

### Point Selection

```python
# Get forecast for a specific location (London)
london_forecast = ds.sel(
    latitude=51.5,
    longitude=-0.1,
    method="nearest"
)

# Extract temperature timeseries
temp_forecast = london_forecast["temperature_2m"]
print(f"Current: {temp_forecast.isel(lead_time=0).values:.1f} K")
print(f"24h forecast: {temp_forecast.sel(lead_time='1 days').values:.1f} K")
```

### Regional Subset

```python
# Extract European region
europe = ds.sel(
    latitude=slice(70, 35),
    longitude=slice(-10, 40)
)

# Calculate wind speed from components
europe["wind_speed_10m"] = (
    (europe["wind_u_10m"]**2 + europe["wind_v_10m"]**2)**0.5
)
```

### Visualization

```python
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

# Plot global temperature at 24h lead time
fig, ax = plt.subplots(
    subplot_kw={'projection': ccrs.Robinson()},
    figsize=(15, 8)
)

ds["temperature_2m"].sel(lead_time="1 days").plot(
    ax=ax,
    transform=ccrs.PlateCarree(),
    cmap="RdYlBu_r",
    cbar_kwargs={'label': 'Temperature (K)'}
)

ax.coastlines()
ax.gridlines(draw_labels=True)
plt.title("ECMWF IFS Temperature Forecast (+24h)")
plt.show()
```

## Dimensions

| Dimension | Range | Resolution | Description |
|-----------|-------|------------|-------------|
| `latitude` | 90°N to 90°S | 0.25° | North-south coordinate (721 points) |
| `longitude` | 0°E to 359.75°E | 0.25° | East-west coordinate (1440 points) |
| `lead_time` | 0-240 hours* | 3h/6h† | Forecast lead time from initialization |
| `init_time` | Rolling 48h | 6 hours | Forecast initialization time (UTC) |

*00z/12z runs only; 06z/18z runs have 0-90h
†3-hourly 0-144h, 6-hourly 150-240h

## Variables

| Variable | Description | Units | Dimensions |
|----------|-------------|-------|------------|
| `temperature_2m` | Air temperature at 2 meters above surface | K | (init_time, lead_time, latitude, longitude) |
| `dewpoint_2m` | Dewpoint temperature at 2 meters | K | (init_time, lead_time, latitude, longitude) |
| `wind_u_10m` | Eastward wind component at 10 meters | m/s | (init_time, lead_time, latitude, longitude) |
| `wind_v_10m` | Northward wind component at 10 meters | m/s | (init_time, lead_time, latitude, longitude) |
| `mean_sea_level_pressure` | Atmospheric pressure reduced to mean sea level | Pa | (init_time, lead_time, latitude, longitude) |
| `surface_pressure` | Atmospheric pressure at surface | Pa | (init_time, lead_time, latitude, longitude) |
| `total_precipitation` | Accumulated precipitation since forecast start | m | (init_time, lead_time, latitude, longitude) |
| `total_column_water_vapour` | Vertically integrated water vapor | kg/m² | (init_time, lead_time, latitude, longitude) |
| `surface_solar_radiation_downwards` | Accumulated downward solar radiation at surface | J/m² | (init_time, lead_time, latitude, longitude) |

## Data Access Patterns

### Temporal Access
The dataset maintains a rolling 48-hour window of forecasts, retaining the 5 most recent initialization times. This provides both current short-range forecasts and recent medium-range outlooks.

### Chunking Strategy
Data is chunked for efficient cloud access:
- `init_time`: 1 (single forecast run)
- `lead_time`: 24 steps (~3 days for 3-hourly data)
- `latitude`: 360 points (~90° of latitude)
- `longitude`: 720 points (~180° of longitude)

Typical chunk size: ~15-20 MB compressed

### Performance Tips
- For time series at specific locations: Select spatial coordinates first, then slice temporally
- For spatial maps at specific times: Use `.sel(lead_time=...)` followed by spatial subsetting
- For regional analysis: Subset latitude/longitude early to reduce data transfer
- Enable Dask for lazy loading: `chunks=None` loads data into memory only when computed

## Pipeline Architecture

### Automation
Data updates run automatically via GitHub Actions:
- **Schedule:** 05, 11, 17, 23 UTC (accounts for 8-11 hour ECMWF data delay)
- **Process:** Download GRIB2 → Convert to Zarr → Validate → Publish
- **Storage:** GitHub repository with GitHub Pages serving

### Update Workflow
1. Query ECMWF Open Data for latest available forecast
2. Download GRIB2 files with all parameters and forecast steps
3. Process with cfgrib and xarray
4. Write/update Zarr store with rolling retention
5. Generate preview visualizations
6. Commit and deploy to GitHub Pages

### Local Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Install system libraries (Ubuntu/Debian)
sudo apt-get install libeccodes-dev

# Run manual update
python -m reformatters update

# Validate dataset
python -m reformatters validate

# View dataset info
python -m reformatters info
```

## Technical Details

### Data Source
- **Provider:** European Centre for Medium-Range Weather Forecasts (ECMWF)
- **Dataset:** ECMWF Open Data - IFS High-Resolution Forecast
- **Access Method:** [ecmwf-opendata](https://github.com/ecmwf/ecmwf-opendata) Python client
- **Dissemination:** ~8-11 hours after forecast initialization
- **License:** [Creative Commons CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)

### Storage Format
- **Format:** Zarr v2 (numcodecs compatible)
- **Compression:** Blosc (zstd, level 3, byte shuffle)
- **Metadata:** CF-1.7 conventions
- **Consolidation:** Consolidated metadata for efficient remote access

### Quality & Validation
Each update includes automated validation:
- Coordinate ranges and ordering
- Variable presence and data types
- Temporal consistency
- Spatial coverage completeness
- Chunk structure verification

## Attribution & References

### Data Attribution
When using this dataset, please cite:
> European Centre for Medium-Range Weather Forecasts (ECMWF). *ECMWF Open Data: Real-time forecasts.* Retrieved from https://www.ecmwf.int/en/forecasts/datasets/open-data

### Related Resources
- [ECMWF Open Data Documentation](https://confluence.ecmwf.int/display/DAC/ECMWF+open+data)
- [IFS Documentation](https://www.ecmwf.int/en/forecasts/documentation-and-support/changes-ecmwf-model)
- [dynamical.org](https://dynamical.org) - Inspiration for architecture

### Implementation
- **Architecture:** Inspired by [dynamical.org](https://dynamical.org)
- **Libraries:** [xarray](http://xarray.pydata.org/), [zarr](https://zarr.dev/), [cfgrib](https://github.com/ecmwf/cfgrib), [ecmwf-opendata](https://github.com/ecmwf/ecmwf-opendata)
- **Hosting:** GitHub Pages
- **Automation:** GitHub Actions

## Support & Contact

**Issues:** Report bugs or request features at [GitHub Issues](https://github.com/<username>/ecmwf_open_data_to_zarr/issues)

**Updates:** Follow repository for notifications on data availability and pipeline changes

**License:** BSD-3-Clause (code), CC-BY-4.0 (data)

---

*Last updated: November 2025*
