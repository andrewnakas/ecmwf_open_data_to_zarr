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

**Issue:** `ecmwf-opendata` download fails
**Solution:** Check ECMWF data availability (data is ~1 hour behind model run time)

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
- Data available: ~1 hour after run time
- Pipeline runs: 1 hour after data availability

---

## Files Modified

1. `src/reformatters/common/template_config.py` - Fixed template generation, forced Zarr v2
2. `src/reformatters/common/region_job.py` - Fixed write logic, forced Zarr v2
3. `src/reformatters/ecmwf/ifs/forecast_15_day/region_job.py` - Simplified to bulk download

All fixes committed to: `claude/ecmwf-zarr-pipeline-019dd7ASphVvcTkojH919dK3`
