# Bug Fixes - ECMWF Pipeline

## Issues Fixed

### 1. Template Generation Error
**Problem:** `ValueError: dimensions ('init_time', 'lead_time', 'latitude', 'longitude') must have the same length as the number of data dimensions, ndim=0`

**Cause:** In `template_config.py`, we were creating xarray Variables with `data=None`, which creates a 0-dimensional array, but specifying 4 dimensions.

**Fix:** Now creates properly shaped numpy arrays filled with the appropriate fill values:
```python
shape = tuple(len(coords[dim]) for dim in dims)
if np.isnan(fill_value):
    data = np.full(shape, np.nan, dtype=np.float32)
else:
    data = np.full(shape, fill_value, dtype=np.float32)
```

**File:** `src/reformatters/common/template_config.py`

---

### 2. Initial Zarr Write Error
**Problem:** First write after creating template would fail because it tried to use `mode="r+"` with region selection on an empty template.

**Cause:** The write logic didn't distinguish between first write and append operations.

**Fix:** Added logic to detect first write and use `mode="w"` to replace the template:
```python
existing = xr.open_zarr(self.zarr_store)
if len(existing.init_time) == 1:
    # First real data write - replace the template
    ds.to_zarr(self.zarr_store, mode="w", consolidated=True)
else:
    # Append mode
    ds.to_zarr(self.zarr_store, mode="r+", region=region, consolidated=False)
```

**File:** `src/reformatters/common/region_job.py`

---

### 3. ECMWF Bulk Download Simplification
**Problem:** Individual parameter downloads were failing with "No parameters could be downloaded" error. Only one GRIB file was downloaded instead of the full forecast.

**Cause:** Looping through parameters individually was unreliable and didn't align with how ecmwf-opendata package is designed to work.

**Fix:** Use the package's native bulk download capability - download all parameters in a single request:
```python
# Single bulk download of all parameters
self.client.retrieve(
    date=coord.init_time.strftime("%Y-%m-%d"),
    time=coord.init_time.hour,
    type="fc",  # forecast
    param=self.PARAMETERS,  # All parameters at once
    target=str(cache_file),
)
```

**Benefits:**
- Single GRIB file with all parameters and lead times
- More reliable downloads
- Simpler code - removed need for `self.downloaded_files` dict
- Faster execution - one API call instead of 8 separate calls
- Uses ecmwf-opendata package as intended

**Changes:**
- Removed individual parameter download loop
- Simplified read_data to handle single multi-parameter GRIB file
- cfgrib automatically splits into datasets by type/level and merges them

**File:** `src/reformatters/ecmwf/ifs/forecast_15_day/region_job.py`

---

### 4. ECMWF Data Availability Delay (404 Errors)
**Problem:** 404 errors when trying to download ECMWF forecast data. Error: `HTTPError: 404 Client Error: Not Found for url: https://data.ecmwf.int/forecasts/...`

**Cause:** ECMWF Open Data has significant delays:
- Data available **7-9 hours** after forecast start time
- Additional **1-2 hour** delay for open data distribution
- Total delay: **~8-11 hours** after model run time

Trying to fetch "latest" run immediately after it starts fails because data isn't published yet.

**Fix:** Two-part solution:

1. **Conservative time calculation** - Go back 12 hours in operational mode:
```python
# Account for 8-11 hour data delay
now = datetime.utcnow()
available_time = now - timedelta(hours=12)
latest_run_hour = max([h for h in run_hours if h <= available_time.hour])
```

2. **Automatic fallback** - If 404 occurs, use client's latest detection:
```python
except Exception as e:
    if "404" in str(e):
        # Use client's automatic latest detection
        result = self.client.retrieve(
            type="fc",
            param=self.PARAMETERS,  # No date/time specified
            target=str(cache_file),
        )
        actual_time = result.datetime  # Get what was actually downloaded
```

**Benefits:**
- Robust handling of data delays
- Automatic fallback if timing calculation is off
- Always gets the latest AVAILABLE data
- Clear error messages about what's happening

**File:** `src/reformatters/ecmwf/ifs/forecast_15_day/region_job.py`

---

### 5. GRIB Multi-Level Merge Conflict
**Problem:** `MergeError: conflicting values for variable 'heightAboveGround' on objects to be combined`

**Cause:** cfgrib splits multi-parameter GRIB files into separate datasets by level:
- 10m level (wind variables: 10u, 10v) → heightAboveGround = 10
- 2m level (temperature, dewpoint: 2t, 2d) → heightAboveGround = 2
- Surface level (pressure, precip: sp, msl, tp, tcc) → different coordinates

When xr.merge() tries to combine these, it finds conflicting height coordinate values.

**Fix:** Drop conflicting height coordinates before merging (height info already in variable names):
```python
# Clean each dataset before merge
cleaned_datasets = []
for ds_part in ds_list:
    coords_to_drop = [c for c in ['heightAboveGround', 'level', 'isobaricInhPa']
                     if c in ds_part.coords]
    if coords_to_drop:
        ds_part = ds_part.drop_vars(coords_to_drop)
    cleaned_datasets.append(ds_part)

# Merge with compat='override' for any remaining conflicts
ds = xr.merge(cleaned_datasets, compat='override')
```

**Benefits:**
- Successful merge of multi-level parameters
- Cleaner dataset (no redundant height coords)
- Height information preserved in variable names (e.g., `wind_u_10m`, `temperature_2m`)

**File:** `src/reformatters/ecmwf/ifs/forecast_15_day/region_job.py`

---

### 6. Missing init_time Coordinate in Zarr
**Problem:** `KeyError: "no index found for coordinate 'init_time'"` when generating previews from zarr store.

**Cause:** Variable selection (`ds = ds[available_vars]`) was happening before `expand_dims(init_time=...)`, causing the init_time coordinate to be dropped or not properly indexed.

**Fix:** Reorder operations to ensure init_time coordinate is preserved:
```python
# 1. Select variables first
wanted_vars = list(self.PARAM_MAP.values())
available_vars = [v for v in wanted_vars if v in ds.data_vars]
ds = ds[available_vars]

# 2. Then add init_time dimension
if "init_time" not in ds.coords:
    ds = ds.expand_dims(init_time=[pd.Timestamp(coord.init_time)])

# 3. Ensure it's indexed
if "init_time" in ds.dims and "init_time" not in ds.indexes:
    ds = ds.set_coords("init_time")
```

**Benefits:**
- init_time coordinate properly preserved in zarr store
- Preview generation can select by init_time
- Consistent coordinate structure

**Additional Fix - Backward Compatibility:**
Updated `generate_previews.py` to handle both indexed and non-indexed init_time:
```python
try:
    latest_ds = ds.sel(init_time=latest_init)
except KeyError:
    # Fallback for old zarr stores without indexed init_time
    latest_idx = int(ds.init_time.argmax().values)
    latest_ds = ds.isel(init_time=latest_idx)
```

**Files:**
- `src/reformatters/ecmwf/ifs/forecast_15_day/region_job.py`
- `src/reformatters/generate_previews.py`

---

### 7. Preview Generation with Missing Variables
**Problem:** Preview generation crashes when expected variables (temperature_2m, wind_u_10m, etc.) are not present in zarr store.

**Cause:** Old zarr stores may have been created with incomplete data before all fixes were deployed. The preview generation assumed all variables would always be present.

**Fix:** Add graceful handling for missing variables:
```python
# Check if variable exists before generating preview
if "temperature_2m" in latest_ds:
    print("Generating temperature map...")
    generate_temperature_map(latest_ds, output_dir, metadata)
else:
    print("Skipping temperature map (temperature_2m not available)")
```

**Benefits:**
- Preview generation succeeds even with incomplete data
- Clear logging of what's skipped and why
- Generates whatever previews are possible with available variables
- Next data update with fixed code will write all variables correctly

**Note:** Existing zarr stores may need to be regenerated to get all variables. The fixed download/processing code will write complete data going forward.

**File:** `src/reformatters/generate_previews.py`

---

### 8. Missing Forecast Lead Times and Parameters
**Problem:** Download only retrieved step=0 (initial time) instead of full forecast range. Only 3 variables downloaded instead of 7. Error message: `No index entries for param=tcc`.

**Cause:** Multiple issues:
1. Missing `step` parameter in retrieve() call - defaults to step=0 only
2. Parameter "tcc" (total cloud cover) not available in ECMWF Open Data
3. Only 00z/12z runs have long-range forecasts (0-240h); 06z/18z runs limited to 0-90h
4. lead_time coordinate not indexed, causing preview generation failures

**Fix:** Multiple changes to download and preview code:

1. **Add step parameter** to download all forecast lead times:
```python
# Generate forecast steps: 0-144h every 3h, then 150-240h every 6h
self.forecast_steps = list(range(0, 145, 3)) + list(range(150, 241, 6))

self.client.retrieve(
    date=date,
    time=time,
    type="fc",
    param=self.PARAMETERS,
    step=self.forecast_steps,  # Download all lead times
    target=str(cache_file),
)
```

2. **Remove unsupported parameter** and restrict to 00z/12z runs:
```python
# Removed "tcc" from parameters list (not available)
PARAMETERS = ["2t", "10u", "10v", "tp", "sp", "msl", "2d"]  # 7 parameters

# Only use 00z/12z runs (have 0-240h forecasts)
run_hours = [0, 12]  # Not [0, 6, 12, 18]
```

3. **Safe lead_time selection** in preview generation:
```python
def safe_select_lead_time(data_array, lead_time_hours):
    """Handle both indexed and non-indexed lead_time coordinates."""
    try:
        return data_array.sel(lead_time=pd.Timedelta(hours=lead_time_hours))
    except (KeyError, ValueError):
        # Fallback to positional selection
        target_lead = pd.Timedelta(hours=lead_time_hours)
        lead_times = data_array.lead_time.values
        idx = int(np.argmin(np.abs(lead_times - target_lead)))
        return data_array.isel(lead_time=idx)
```

**Benefits:**
- Downloads complete 10-day forecast (65 steps: 0-240h)
- Gets all 7 available parameters
- Robust preview generation with fallback for non-indexed coordinates
- Clear logging of forecast steps and parameters

**Files:**
- `src/reformatters/ecmwf/ifs/forecast_15_day/region_job.py`
- `src/reformatters/generate_previews.py`

---

## Testing Recommendations

### Local Testing
```bash
# Install dependencies
pip install -e ".[dev]"

# Install system dependencies (Ubuntu/Debian)
sudo apt-get install libeccodes-dev libeccodes-tools

# Run update
python -m reformatters update

# Validate
python -m reformatters validate
```

### Expected Workflow
1. Template created with proper dimensions (1, 85, 721, 1440)
2. ECMWF data downloaded (single GRIB file with all 8 parameters and all lead times)
3. GRIB file read with cfgrib (automatically splits into multiple datasets by type/level)
4. Datasets merged into single xarray Dataset
5. Data written to zarr with mode="w" (first time)
6. Subsequent updates use mode="r+" with region selection

### Common Issues

**Issue:** `libeccodes not found`
**Solution:** Install eccodes system library

**Issue:** `ecmwf-opendata` download fails with 404 error
**Solution:** ECMWF data has 8-11 hour delay. Code now accounts for this automatically.

**Issue:** `cfgrib` can't read GRIB
**Solution:** Ensure GRIB file is valid and not corrupted during download

**Issue:** Zarr write fails with dimension mismatch
**Solution:** Check that standardized coordinates match template dimensions

---

## Architecture Summary

**Three-Class Pattern (from dynamical.org):**

1. **TemplateConfig** (`template_config.py`)
   - Defines dataset structure (dimensions, coordinates, variables)
   - Generates properly shaped template arrays
   - Specifies encoding (Blosc compression, chunking)

2. **RegionJob** (`region_job.py`)
   - Downloads GRIB files from ECMWF (parameter by parameter)
   - Reads GRIB with cfgrib
   - Standardizes coordinates
   - Writes to zarr (mode="w" first time, mode="r+" for appends)

3. **Dataset** (`dataset.py`)
   - Orchestrates TemplateConfig + RegionJob
   - Handles update() and backfill() operations
   - Manages validation

**Data Flow:**
```
ECMWF API → GRIB2 files → cfgrib → xarray Dataset → Zarr store
```

**Update Schedule:**
- GitHub Actions: 05, 11, 17, 23 UTC (every 6 hours)
- ECMWF runs: 00, 06, 12, 18 UTC
- Data available: ~8-11 hours after run time (7-9h processing + 1-2h open data delay)
- Pipeline runs: Requests forecast from 12 hours ago to ensure availability

---

## Files Modified

1. `src/reformatters/common/template_config.py` - Fixed template generation, forced Zarr v2
2. `src/reformatters/common/region_job.py` - Fixed write logic, forced Zarr v2
3. `src/reformatters/ecmwf/ifs/forecast_15_day/region_job.py` - Simplified to bulk download

All fixes committed to: `claude/ecmwf-zarr-pipeline-019dd7ASphVvcTkojH919dK3`
