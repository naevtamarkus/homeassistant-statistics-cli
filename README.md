# Home Assistant Statistics Data CLI for the Recorder DB

[![GitHub license](https://img.shields.io/github/license/yourusername/ha-data-cli)](https://github.com/yourusername/ha-data-cli/blob/main/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/yourusername/ha-data-cli)](https://github.com/yourusername/ha-data-cli/issues)
[![GitHub stars](https://img.shields.io/github/stars/yourusername/ha-data-cli)](https://github.com/yourusername/ha-data-cli/stargazers)

A command-line interface (CLI) for managing Home Assistant sensor data, addressing gaps in the built-in data management capabilities of statistics data in the Recorder. This tool helps with data exploration, analysis, modification, and migration tasks that aren't available in the Home Assistant UI. 


## ⚠️ IMPORTANT: Database Safety Warning

**ALWAYS BACK UP YOUR HOME ASSISTANT DATABASE BEFORE MAKING MODIFICATIONS.**

This tool can make permanent changes to your Home Assistant database. While it includes safety features like `--dry-run`, unintended modifications could affect your Home Assistant installation or cause data loss. It's strongly recommended to:

1. Create a complete backup of your Home Assistant instance
2. Work on a copy of your database when possible
3. Use the `--dry-run` option to preview changes before applying them

## 🔍 Actions available in the CLI

- **Status**: Examine database structure, size, and record counts
- **List**: List all entities with storage metrics and time ranges
- **Export**: Export entity data with flexible filtering options
- **Import**: Import and modify sensor data with safety features

## 📊 Use Cases

- **Storage Analysis**: Find which sensors are using the most database space
- **Data Cleanup**: Remove or modify incorrect sensor readings
- **Data Migration**: Export data from one sensor and import to another or merge data between instances
- **Value Filtering**: Find readings outside normal ranges
- **Offline Modifications**: Copy database to a PC, modify data safely, and apply changes with SQL
- **Missing Data Recovery**: Fix gaps in energy or sensor data by adding missing records
- **External Visualization and Analysis**: Extract data for use with external tools (e.g. Excel)

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/naevtamarkus/cli_ha_statistics.git
cd cli_ha_statistics

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install click sqlalchemy tabulate
```

## 📝 Configuration

By default, the tool looks for a Home Assistant database at `./home-assistant_v2.db`. You can specify a different database location using the `--db-url` option or by setting the `HA_DB_URL` environment variable:

```bash
# Using --db-url option
python cli_ha_statistics.py --db-url="sqlite:///path/to/home-assistant_v2.db" status

# Using environment variable
export HA_DB_URL="sqlite:///path/to/home-assistant_v2.db"
python cli_ha_statistics.py status
```

## 📋 Commands

### Status

Get an overview of your database tables, including row counts and size estimates:

```bash
python cli_ha_statistics.py status
```

Example output:
```
Database type: sqlite, schema 50
Time: 2025-05-17 12:34:56 UTC
----------------------------------------------------------------------
Table                  Rows    Cols  Records  % total  ~ MB
events                 52394    6    314364   34.5%    2.4
statistics            120840    9   1087560   25.7%    8.3
states                 45983    8    367864   12.2%    2.8
statistics_short_term  28475    9    256275    7.4%    2.0
...
----------------------------------------------------------------------
TOTAL RECORDS: 3,125,489
TOTAL SIZE: 23.80 MB
```

### List

List entities in the database with stats about record counts and storage:

```bash
python cli_ha_statistics.py list [--sort COLUMN] [--reverse] [--csv] [--after DATE] [--before DATE]
```

Options:
- `--sort`: Sort by column (`count`, `first`, `last`, or `kb`)
- `--reverse`: Reverse sort order
- `--csv`: Output in CSV format
- `--after`: Only include records after this date
- `--before`: Only include records before this date

Example output:
```
Entity                           Count  First               Last                ~ KB  Unit
sensor.temperature_living_room   86400  2025-01-01 00:00:00 2025-05-17 12:30:00 775.2 °C
sensor.humidity_bathroom         84960  2025-01-01 00:00:00 2025-05-17 12:30:00 764.6 %
sensor.power_consumption         43200  2025-03-01 00:00:00 2025-05-17 12:30:00 388.8 W
...
```

### Export

Export records for specific entities with filtering options:

```bash
python cli_ha_statistics.py export ENTITY [ENTITY...] [--above VALUE] [--below VALUE] [--after DATE] [--before DATE] > export.csv
```

Options:
- `--above VALUE`: Only include records with values strictly above threshold
- `--below VALUE`: Only include records with values strictly below threshold
- `--after DATE`: Only include records after this date
- `--before DATE`: Only include records before this date

Example:
```bash
# Export temperature readings above 25°C from April 2025
python cli_ha_statistics.py export sensor.temperature_living_room --above 25 --after "2025-04-01" > high_temps.csv
```

### Import

Import (and modify) records from a CSV file:

```bash
python cli_ha_statistics.py import file.csv [--dry-run]
```

Options:
- `--dry-run`: Preview changes without modifying the database

The import function performs an "upsert" operation - it updates existing records or inserts new ones, and can delete records with matching IDs when appropriate fields are provided.

## 📝 CSV Format

Export format (also used for import):
```
table,entity (ignored),date (ignored),id,created,created_ts,metadata_id,start,start_ts,mean,min,max,last_reset,last_reset_ts,state,sum,mean_weight
statistics,sensor.helm_memory_available_swap,2024-01-03 11:00:00,7,,1704283210.3089955,7,,1704279600.0,3198.373888,3198.373888,3198.373888,,,,,
statistics,sensor.helm_memory_available_swap,2024-01-03 12:00:00,23,,1704286810.3039548,7,,1704283200.0,3198.3738880000005,3198.373888,3198.373888,,,,,
statistics,sensor.helm_memory_available_swap,2024-01-03 13:00:00,39,,1704290410.304482,7,,1704286800.0,3198.3738880000005,3198.373888,3198.373888,,,,,```

For import, only the fields you want to modify are required (mainly `table`, `id` for updates, plus values).

## 📊 Example Use Cases

### Finding sensors using the most storage

```bash
python cli_ha_statistics.py list --sort kb
```

### Find abnormal temperature readings

```bash
python cli_ha_statistics.py export sensor.temperature_living_room --above 30 --below 10 > abnormal_temps.csv
```

### Correcting wrong sensor readings

1. Export the data you need to modify:
   ```bash
   python cli_ha_statistics.py export sensor.temperature_living_room --after "2025-05-01" > temp.csv
   ```

2. Edit the CSV file to correct values

3. Preview changes without modifying the database:
   ```bash
   python cli_ha_statistics.py import temp.csv --dry-run
   ```

4. Apply the changes:
   ```bash
   python cli_ha_statistics.py import temp.csv
   ```

### Filling in missing energy data

1. Export a time range containing the gap:
   ```bash
   python cli_ha_statistics.py export sensor.energy_consumption --after "2025-04-01" --before "2025-04-30" > energy.csv
   ```

2. In Excel/spreadsheet software:
   - Identify missing time periods
   - Add new rows without IDs (leave ID field empty)
   - Set appropriate timestamps and values
   - Save the CSV

3. Preview and import the fixed data:
   ```bash
   python cli_ha_statistics.py import energy.csv --dry-run
   python cli_ha_statistics.py import energy.csv
   ```

### Migrating data between sensors

For example, when you replace a sensor but want to keep the history:

1. Export data from both sensors:
   ```bash
   python cli_ha_statistics.py export sensor.old_temperature > old_sensor.csv
   python cli_ha_statistics.py export sensor.new_temperature > new_sensor.csv
   ```

2. In a text editor or spreadsheet, edit the `old_sensor.csv` file:
   - Remove the rows you don't want to migrate to the new sensor
   - Remove the ID column values (or set to empty) to create new records, leaving the data and dates untouched
   - Change the metadata_id of all entries of the old sensor to match that of the `new_sensor.csv`

3. Import the modified data:
   ```bash
   python cli_ha_statistics.py import old_sensor.csv --dry-run
   python cli_ha_statistics.py import old_sensor.csv
   ```

### Offline modifications with SQL generation

For safer modifications on a production system:

1. Copy your Home Assistant database to a separate computer:
   ```bash
   scp homeassistant@homeassistant:/config/home-assistant_v2.db ./
   ```

2. Work locally and eventually run the import with dry-run to generate SQL statements:
   ```bash
   python cli_ha_statistics.py import fixes.csv --dry-run > sql_fixes.sql
   ```

3. Review the SQL statements for correctness

4. Apply the SQL directly to your production database:
   ```bash
   # For SQLite
   sqlite3 /path/to/home-assistant_v2.db < sql_fixes.sql
   
   # Or through Home Assistant's database shell
   ha database execute < sql_fixes.sql
   ```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgements

- [Home Assistant](https://www.home-assistant.io/) for the amazing home automation platform
- [SQLAlchemy](https://www.sqlalchemy.org/) for the database toolkit
- [Click](https://click.palletsprojects.com/) for the command-line interface
- [Tabulate](https://github.com/astanin/python-tabulate) for pretty-printing tabular data
