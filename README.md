# ECMWF Open Data to Zarr

Automated pipeline to convert ECMWF Open Data real-time forecasts to cloud-optimized Zarr format, inspired by [dynamical.org](https://dynamical.org).

## Overview

This project provides:
- **Automated data pipeline**: GitHub Actions pulls ECMWF IFS forecasts every 6 hours
- **Zarr format**: Cloud-optimized, chunked storage for efficient access
- **Public access**: Data served via GitHub Pages at `https://<username>.github.io/ecmwf_open_data_to_zarr/`
- **Clean architecture**: Following dynamical.org's three-class pattern (TemplateConfig, RegionJob, Dataset)

## Data Specifications

### ECMWF IFS High-Resolution Forecast

- **Model**: ECMWF Integrated Forecasting System (IFS)
- **Resolution**: 0.25° (~25 km)
- **Update frequency**: Every 6 hours (00, 06, 12, 18 UTC)
- **Forecast horizon**: 15 days (360 hours)
- **Temporal resolution**: 3-hourly (0-144h), 6-hourly (150-360h)
- **Coverage**: Global
- **Format**: Zarr v3 with Blosc compression

### Available Variables

- Temperature (2m, max, min)
- Wind components (10m, 100m, U/V)
- Precipitation (total, convective)
- Pressure (surface, mean sea level)
- Cloud cover
- Humidity (2m, relative)
- Radiation fluxes
- Geopotential height (pressure levels)

## Installation

```bash
# Clone the repository
git clone https://github.com/<username>/ecmwf_open_data_to_zarr.git
cd ecmwf_open_data_to_zarr

# Install dependencies (Python 3.12+ required)
pip install -e ".[dev]"
```

## Usage

### Accessing the Data

```python
import xarray as xr

# Open the latest forecast
ds = xr.open_zarr(
    "https://<username>.github.io/ecmwf_open_data_to_zarr/data/ecmwf/ifs/forecast-15-day/latest.zarr",
    decode_timedelta=True,
    chunks=None  # Load chunks into memory for point selections
)

# Select a location (e.g., London)
london = ds.sel(latitude=51.5, longitude=-0.1, method="nearest")

# Plot temperature forecast
london["temperature_2m"].plot(x="valid_time")
```

### Running the Pipeline Locally

```bash
# Update the latest forecast
ecmwf-zarr ecmwf-ifs-forecast-15-day update

# Backfill historical data
ecmwf-zarr ecmwf-ifs-forecast-15-day backfill --end-date 2025-01-01

# Validate dataset
ecmwf-zarr ecmwf-ifs-forecast-15-day validate
```

## Architecture

Following dynamical.org's design patterns:

```
src/reformatters/
├── common/
│   ├── template_config.py   # Define zarr structure and metadata
│   ├── region_job.py         # Download, process, write data
│   └── dataset.py            # Orchestrate complete workflow
└── ecmwf/
    └── ifs/
        └── forecast_15_day/
            ├── template_config.py  # ECMWF-specific configuration
            ├── region_job.py       # GRIB download & conversion
            └── dataset.py          # Dataset orchestration
```

### Three-Class Pattern

1. **TemplateConfig**: Defines dataset structure (dimensions, coordinates, variables)
2. **RegionJob**: Handles downloading GRIB files and converting to Zarr chunks
3. **Dataset**: Orchestrates the complete workflow (update, backfill, validate)

## Automation

### GitHub Actions Schedule

The pipeline runs automatically via GitHub Actions:

- **Schedule**: Every 6 hours at 05, 11, 17, 23 UTC (1 hour after ECMWF data release)
- **Workflow**: `.github/workflows/update-data.yml`
- **Validation**: Automatic checks after each update

### Manual Trigger

You can manually trigger an update via GitHub Actions:
1. Go to Actions tab
2. Select "Update ECMWF Data"
3. Click "Run workflow"

## Data Access Patterns

See [`notebooks/example_access.ipynb`](notebooks/example_access.ipynb) for detailed examples:

- Point selection for specific locations
- Regional subsetting
- Time series analysis
- Visualization with matplotlib/cartopy
- Multi-variable analysis

## Contributing

Contributions welcome! This project follows the patterns established by [dynamical-org/reformatters](https://github.com/dynamical-org/reformatters).

## License

BSD-3-Clause License. Data from ECMWF is provided under CC-BY-4.0 license.

## Acknowledgments

- Architecture inspired by [dynamical.org](https://dynamical.org)
- Data provided by [ECMWF Open Data](https://www.ecmwf.int/en/forecasts/datasets/open-data)
- Built with [xarray](http://xarray.pydata.org/), [zarr](https://zarr.dev/), and [ecmwf-opendata](https://github.com/ecmwf/ecmwf-opendata)
