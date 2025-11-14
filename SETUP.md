# Setup Guide

Complete guide to getting the ECMWF Open Data to Zarr pipeline running on GitHub.

## Prerequisites

- GitHub account
- GitHub repository with Actions enabled
- (Optional) Python 3.12+ for local testing

## Step 1: Enable GitHub Pages

1. Go to your repository on GitHub
2. Click **Settings** → **Pages**
3. Under "Build and deployment":
   - **Source**: Select "GitHub Actions"
4. Save the settings

## Step 2: Configure GitHub Actions

The workflows are already set up in `.github/workflows/`:

- `update-data.yml` - Runs every 6 hours to fetch new ECMWF data
- `deploy-pages.yml` - Deploys data and docs to GitHub Pages

### Enable Workflows

1. Go to the **Actions** tab in your repository
2. If prompted, click "I understand my workflows, go ahead and enable them"
3. The workflows will now run automatically

## Step 3: First Run

### Option A: Automatic (Wait for Schedule)

The `update-data.yml` workflow runs automatically at:
- 05:00 UTC
- 11:00 UTC
- 17:00 UTC
- 23:00 UTC

Wait for the next scheduled time, and the workflow will run automatically.

### Option B: Manual Trigger

1. Go to **Actions** tab
2. Select "Update ECMWF Data" workflow
3. Click "Run workflow" button
4. Click the green "Run workflow" button in the dropdown
5. Wait for the workflow to complete (may take 15-30 minutes for first run)

## Step 4: Verify Deployment

After the workflow completes:

1. Check the **Actions** tab for green checkmarks
2. Go to **Settings** → **Pages** to find your site URL
3. Visit: `https://YOUR_USERNAME.github.io/ecmwf_open_data_to_zarr/`

You should see the data portal landing page.

## Step 5: Access Your Data

Update the example code with your username:

```python
import xarray as xr

ds = xr.open_zarr(
    "https://YOUR_USERNAME.github.io/ecmwf_open_data_to_zarr/data/ecmwf/ifs/forecast-15-day/latest.zarr",
    decode_timedelta=True,
    chunks=None
)

print(ds)
```

## Local Development

### Install Dependencies

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/ecmwf_open_data_to_zarr.git
cd ecmwf_open_data_to_zarr

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package with dev dependencies
pip install -e ".[dev]"
```

### System Dependencies (for GRIB support)

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y libeccodes-dev libeccodes-tools
```

**macOS:**
```bash
brew install eccodes
```

**Windows:**
```bash
# Use conda
conda install -c conda-forge eccodes
```

### Run Locally

```bash
# Update template (creates zarr structure)
python -m reformatters update-template

# Fetch latest data
python -m reformatters update

# Validate
python -m reformatters validate

# View info
python -m reformatters info
```

### Run Jupyter Notebooks

```bash
jupyter notebook notebooks/example_access.ipynb
```

## Troubleshooting

### Workflow Fails: "Permission denied"

1. Go to **Settings** → **Actions** → **General**
2. Under "Workflow permissions", select:
   - ✅ Read and write permissions
   - ✅ Allow GitHub Actions to create and approve pull requests
3. Click "Save"

### Workflow Fails: "libeccodes not found"

This is expected in the first run. The workflow installs `libeccodes-dev` automatically.
If it still fails, check the workflow logs.

### Data Not Appearing on GitHub Pages

1. Check that the workflow completed successfully
2. Verify files exist in `data/` directory in your repository
3. GitHub Pages can take 1-2 minutes to rebuild after changes
4. Check **Settings** → **Pages** for deployment status

### Large Repository Size Warning

The zarr files are chunked and compressed, but storing many forecast cycles can grow the repo.
Consider:
- Using Git LFS for large files
- Keeping only recent forecasts (last 7 days)
- Using external storage (S3, etc.) instead of GitHub

## Customization

### Change Update Schedule

Edit `.github/workflows/update-data.yml`:

```yaml
on:
  schedule:
    # Change the cron schedule
    - cron: '0 */6 * * *'  # Every 6 hours
```

Cron syntax: `minute hour day month day-of-week`

### Add More Variables

Edit `src/reformatters/ecmwf/ifs/forecast_15_day/region_job.py`:

```python
PARAMETERS = [
    "2t",   # 2m temperature
    "10u",  # 10m u-wind
    "10v",  # 10m v-wind
    "tp",   # total precipitation
    # Add more ECMWF parameter codes
    "2d",   # 2m dewpoint
    "skt",  # skin temperature
    # ... see ECMWF parameter database
]
```

Then update `template_config.py` to add corresponding variables.

### Change Storage Location

Edit `src/reformatters/ecmwf/ifs/forecast_15_day/dataset.py`:

```python
def __init__(self, storage_path: Path | None = None):
    if storage_path is None:
        storage_path = Path("data/ecmwf/ifs/forecast-15-day")  # Change this
```

## Monitoring

### Check Workflow Status

GitHub Actions will email you if workflows fail. You can also:

1. Add status badge to README.md:

```markdown
![Update Data](https://github.com/YOUR_USERNAME/ecmwf_open_data_to_zarr/actions/workflows/update-data.yml/badge.svg)
```

2. View logs in Actions tab
3. Set up notifications in repository settings

### Data Freshness

The validation step checks if data is < 24 hours old. If older, you'll see a warning in logs.

## Resources

- [ECMWF Open Data Documentation](https://www.ecmwf.int/en/forecasts/datasets/open-data)
- [ecmwf-opendata Python Client](https://github.com/ecmwf/ecmwf-opendata)
- [Xarray Documentation](http://xarray.pydata.org/)
- [Zarr Documentation](https://zarr.readthedocs.io/)
- [dynamical.org Inspiration](https://github.com/dynamical-org/reformatters)

## Support

For issues with:
- **This pipeline**: Open an issue in this repository
- **ECMWF data**: See [ECMWF support](https://www.ecmwf.int/en/forecasts/access-forecasts/access-real-time-open-data)
- **GitHub Pages**: See [GitHub Pages docs](https://docs.github.com/en/pages)
