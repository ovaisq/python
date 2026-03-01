# Transform XLSX

Transforms customer-supplied XLSX files to a Worklete-Dashboard friendly data format.

This script:
1. Reads a user-supplied XLSX file
2. Reads a Worklete Master Roster Google Sheet
3. Transforms data from the user-supplied XLSX into a Worklete Master Roster Google Sheet compliant format

The goal is to help the CS team shorten the time and remove user errors from updating user rosters.

## Installation

### 1. Install Python

- **Windows**: [Download Python 3.8.10](https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe)
  - **Note**: During installation, select the "add to system path" option

### 2. Install Python Modules

a. Open Command Prompt (Windows) or Terminal (macOS)

b. Run the following command:

```bash
pip3 install -r requirements.txt
```

**Note**: If you're running this script for the very first time, you'll be prompted with Google authentication web flow.

## Usage

### Command Line Arguments

| Argument | Description |
|----------|-------------|
| `--orig-excel-file` | Original Excel spreadsheet file name |
| `--google-sheet-id` | Google Sheet ID (extracted from the sheet URL) |
| `--google-cred-json` | Google user credentials JSON file |
| `--org-name` | Organization name (lowercase, e.g., `sheehan`, `cbre`) |

### Extracting Google Sheet ID

From a Google Sheet URL like:
```
https://docs.google.com/spreadsheets/d/1wLhw7FSs95ib2et6LXXXDzl3cM_6ztFaFIFuHxR5LEk/edit#gid=1952452264
```

The Sheet ID is the long string between `/d/` and `/edit`:
```
1wLhw7FSs95ib2et6LXXXDzl3cM_6ztFaFIFuHxR5LEk
```

### Examples

**Windows:**
```bash
python transform_xlsx.py --orig-excel-file "your_file.xlsx" --google-sheet-id <your-sheet-id> --google-cred-json <credentials.json> --org-name <org-name>
```

**macOS:**
```bash
./transform_xlsx.py --orig-excel-file "your_file.xlsx" --google-sheet-id <your-sheet-id> --google-cred-json <credentials.json> --org-name <org-name>
```

## Supported Organizations

The script currently supports the following organization formats:
- `sheehan` - Transforms data with custom name parsing and location-based sorting
- `cbre` - Transforms data using existing email IDs and group-based structure

## Output

The script generates a new XLSX file containing only the new users (those not already present in the Google Sheet). The output file is named with a timestamp prefix:

```
<timestamp>_<org-name>_difference_<original-file-name>.xlsx
```

## Requirements

See `requirements.txt` for the full list of Python dependencies.
