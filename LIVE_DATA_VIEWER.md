# Live Data Viewer - Implementation Guide

## Overview

The GitHub Pages now displays **live forecast visualizations** that are automatically updated every 6 hours when new ECMWF data arrives. The page shows:

1. **Latest forecast metadata** (initialization time, status)
2. **Global forecast maps** at 24-hour lead time:
   - Temperature
   - Wind speed
   - Precipitation
3. **15-day city forecasts** (time series charts)
4. **24-hour temperature forecasts** for major cities

## How It Works

### Workflow Automation

The GitHub Actions workflow (`.github/workflows/update-data.yml`) now:

1. **Pulls latest ECMWF data** (runs at 05, 11, 17, 23 UTC)
2. **Converts GRIB2 to Zarr**
3. **Generates preview visualizations** ← NEW!
4. **Commits data and images**
5. **Triggers GitHub Pages rebuild**

The new step in the workflow:

```yaml
- name: Generate preview visualizations
  run: |
    mkdir -p docs/previews
    python src/reformatters/generate_previews.py
  continue-on-error: true
```

### Preview Generation Script

**Location:** `src/reformatters/generate_previews.py`

This script:
- Opens the latest zarr forecast
- Extracts data at 24-hour lead time
- Generates 4 preview images using matplotlib + cartopy
- Saves metadata as JSON
- Outputs to `docs/previews/`

**Generated files:**
```
docs/previews/
├── temperature_24h.png      # Global temperature map
├── wind_speed_24h.png        # Global wind speed map
├── precipitation_24h.png     # Global precipitation map
├── city_forecasts.png        # 15-day city time series
└── latest_forecast.json      # Forecast metadata
```

**Metadata JSON structure:**
```json
{
  "init_time": "2025-01-15T00:00:00",
  "init_time_utc": "2025-01-15 00:00 UTC",
  "generated_at": "2025-01-15 05:23:45 UTC",
  "variables": ["temperature_2m", "wind_u_10m", ...],
  "dimensions": {"init_time": 1, "lead_time": 85, "latitude": 721, "longitude": 1440},
  "forecast_hours": 360,
  "city_temperatures_24h": {
    "New York": 5.2,
    "London": 8.1,
    "Tokyo": 12.5,
    "Sydney": 23.8,
    "São Paulo": 28.3,
    "Mumbai": 27.1
  }
}
```

### Interactive Landing Page

**Location:** `docs/index.html`

Features:
- **JavaScript-powered**: Fetches `latest_forecast.json` on page load
- **Auto-refresh**: Checks for updates every 10 minutes
- **Responsive design**: Works on mobile and desktop
- **Live badges**: Shows "LIVE" and "Auto-Updated" status
- **Graceful fallback**: Shows loading message if images aren't ready yet

**Display sections:**
1. **Forecast Info Card**: Shows init time, generation time, and status
2. **Metadata Cards**: Forecast hours, variable count, grid points
3. **Preview Maps**: 4 large preview images with descriptions
4. **City Temperature Grid**: 6 cities with 24h forecast temps
5. **Data Access Code**: Working Python example
6. **Dataset Info**: Specifications and details

## Timing

### ECMWF Data Release Schedule

- **Model runs:** 00, 06, 12, 18 UTC
- **Data available:** ~1 hour after run time
- **Our workflow runs:** 05, 11, 17, 23 UTC (1 hour after availability)

### Update Timeline (Example)

```
00:00 UTC - ECMWF IFS model runs
01:00 UTC - ECMWF publishes data to AWS S3
05:00 UTC - GitHub Actions workflow triggers
05:05 UTC - Data download begins
05:20 UTC - Zarr conversion completes
05:25 UTC - Preview images generated
05:30 UTC - Files committed and pushed
05:35 UTC - GitHub Pages rebuilds
05:40 UTC - Live page updated with new forecast!
```

Users visiting the page will see:
- **Latest forecast:** Initialized at 00:00 UTC
- **Generated at:** 05:25 UTC
- **Maps showing:** 24-hour forecast (valid at tomorrow 00:00 UTC)

## Customization

### Add More Cities

Edit `src/reformatters/generate_previews.py`:

```python
cities = {
    "New York": (40.7, 286.0),
    "London": (51.5, 359.9),
    "Tokyo": (35.7, 139.7),
    "Sydney": (-33.9, 151.2),
    "São Paulo": (-23.5, 313.4),
    "Mumbai": (19.1, 72.9),
    # Add your cities here:
    "Paris": (48.9, 2.4),
    "Berlin": (52.5, 13.4),
}
```

### Change Map Lead Time

Currently shows 24-hour forecast. To change to 48-hour:

```python
# In generate_previews.py
temp_24h = ds["temperature_2m"].sel(lead_time="24h")  # Change to "48h"
```

### Adjust Map Appearance

Color maps and ranges:
```python
# Temperature map
cmap="RdYlBu_r",  # Red-Yellow-Blue reversed
vmin=-30, vmax=40  # Celsius range

# Wind map
cmap="YlOrRd",  # Yellow-Orange-Red
vmin=0, vmax=25  # m/s range

# Precipitation map
cmap="Blues",
vmin=0, vmax=50  # mm range
```

### Add More Variables

Create new functions in `generate_previews.py`:

```python
def generate_pressure_map(ds, output_dir, metadata):
    """Generate sea level pressure map."""
    msl = ds["mean_sea_level_pressure"].sel(lead_time="24h") / 100  # Pa to hPa

    # Plot similar to other maps...
    output_path = output_dir / "pressure_24h.png"
    plt.savefig(output_path, dpi=150)
```

Then add to the main function:
```python
generate_pressure_map(latest_ds, output_dir, metadata)
```

And update `index.html` to display it:
```html
<div class="preview-card">
    <h3>Sea Level Pressure</h3>
    <div id="pressure-preview">
        <div class="loading">Generating pressure map...</div>
    </div>
</div>
```

```javascript
loadPreviewImage('pressure-preview', 'previews/pressure_24h.png', 'Sea Level Pressure');
```

## Troubleshooting

### Images Not Showing

1. **Check workflow logs:**
   - Go to Actions tab → Latest "Update ECMWF Data" run
   - Check "Generate preview visualizations" step
   - Look for errors in matplotlib/cartopy

2. **Common issues:**
   - `cartopy` not installed: Fallback to basic plots (should still work)
   - zarr file not found: Run update first
   - Memory issues: Reduce image DPI or resolution

3. **Manual test:**
   ```bash
   python src/reformatters/generate_previews.py
   ```

### JSON Not Loading

1. **Check file exists:** `docs/previews/latest_forecast.json`
2. **Verify format:** Valid JSON structure
3. **Browser console:** Check for CORS or fetch errors
4. **GitHub Pages:** May take 1-2 minutes to rebuild

### Old Data Showing

1. **Force refresh:** Ctrl+F5 (or Cmd+Shift+R on Mac)
2. **Check commit time:** Verify data was actually updated
3. **Auto-refresh:** Page refreshes every 10 minutes automatically

## Performance

### Image Sizes

- Temperature map: ~800 KB
- Wind map: ~700 KB
- Precipitation map: ~600 KB
- City forecasts: ~300 KB

**Total:** ~2.5 MB per update

### GitHub Repository Size

With 4 updates/day:
- Images: ~10 MB/day
- Zarr data: Varies (typically 50-200 MB per forecast)

**Recommendation:** Keep last 7 days of forecasts, archive older data

### Page Load Speed

- Initial load: ~3-5 seconds (includes fetching JSON + 4 images)
- Auto-refresh: ~1 second (only JSON fetch)
- Images use lazy loading for faster initial render

## Future Enhancements

Potential additions:

1. **Interactive maps:** Use Leaflet.js + zarr.js for zoomable maps
2. **Animation:** Create GIF/MP4 animations of forecast evolution
3. **Regional views:** Add continent-specific maps (e.g., North America, Europe)
4. **Ensemble data:** If using ECMWF ensemble forecasts, show spread
5. **Comparison:** Side-by-side comparison of different forecast runs
6. **3D visualization:** Height-latitude cross-sections
7. **Custom location:** User can enter coordinates to see local forecast
8. **Historical archive:** Browse previous forecasts

## Resources

- [matplotlib colormaps](https://matplotlib.org/stable/tutorials/colors/colormaps.html)
- [cartopy projections](https://scitools.org.uk/cartopy/docs/latest/reference/projections.html)
- [GitHub Pages custom domain](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site)
- [ECMWF parameter database](https://apps.ecmwf.int/codes/grib/param-db)

## Summary

The live data viewer provides:

✅ **Automatic updates** every 6 hours
✅ **Real-time visualizations** of the latest forecast
✅ **Global and city-level** views
✅ **Interactive web interface** with auto-refresh
✅ **Following dynamical.org patterns** for data display

Users can now visit your GitHub Pages and see the latest ECMWF forecast without writing any code!
