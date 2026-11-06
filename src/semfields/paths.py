"""Central project paths, so notebooks and scripts don't hard-code locations."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

# Raw data (as downloaded, never modified)
GECO_DIR = DATA_DIR / "geco"
MECO_DIR = DATA_DIR / "meco"
SWOW_EN_DIR = DATA_DIR / "swow" / "SWOW-EN18"
SWOW_NL_DIR = DATA_DIR / "swow" / "SWOW-NL"
FREQUENCY_DIR = DATA_DIR / "frequency"

# Derived data
INTERIM_DIR = DATA_DIR / "interim"      # cleaned, cached versions of raw data
PROCESSED_DIR = DATA_DIR / "processed"  # analysis-ready tables (e.g. word x reader with switch variable)

FIGURES_DIR = RESULTS_DIR / "figures"
TABLES_DIR = RESULTS_DIR / "tables"

GECO_DEFINITION = CONFIG_DIR / "geco.yaml"
