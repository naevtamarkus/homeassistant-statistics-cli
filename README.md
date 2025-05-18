# Home Assistant Statistics Data CLI for the Recorder DB

[![GitHub license](https://img.shields.io/github/license/naevtamarkus/homeassistant-statistics-cli)](https://github.com/yourusername/ha-data-cli/blob/main/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/naevtamarkus/homeassistant-statistics-cli)](https://github.com/yourusername/ha-data-cli/issues)
[![GitHub stars](https://img.shields.io/github/stars/naevtamarkus/homeassistant-statistics-cli)](https://github.com/yourusername/ha-data-cli/stargazers)

A command-line interface (CLI) for managing Home Assistant sensor data, addressing gaps in the built-in data management capabilities of statistics data in the Recorder. This tool helps with data exploration, analysis, modification, and migration tasks that aren't available in the Home Assistant UI. 

## 📊 Use Cases

- **Storage Analysis**: Find which sensors are using the most database space
- **Data Cleanup**: Remove or modify incorrect sensor readings
- **Data Migration**: Export data from one sensor and import to another or merge data between instances
- **Value Filtering**: Find readings outside normal ranges
- **Offline Modifications**: Copy database to a PC, modify data safely, and apply changes with SQL
- **Missing Data Recovery**: Fix gaps in energy or sensor data by adding missing records
- **External Visualization and Analysis**: Extract data for use with external tools (e.g. Excel)


## 🔍 Commands available in the CLI

- **Status**: Examine database structure, size, and record counts
- **List**: List all entities with storage metrics and time ranges
- **Export**: Export entity data with flexible filtering options
- **Import**: Import and modify sensor data with safety features


## ⚠️ Database Safety Warning

**ALWAYS BACK UP YOUR HOME ASSISTANT DATABASE BEFORE MAKING MODIFICATIONS.**

This tool can make permanent changes to your Home Assistant database. While it includes safety features like `--dry-run`, unintended modifications could affect your Home Assistant installation or cause data loss. It's strongly recommended to:

1. Create a complete backup of your Home Assistant instance
2. Work on a copy of your database when possible
3. Use the `--dry-run` option to preview changes before applying them


## 🚀 Installation & Configuration

```bash
# Clone the repository
git clone https://github.com/naevtamarkus/homeassistant-statistics-cli.git
cd homeassistant-statistics-cli

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install click sqlalchemy tabulate
```

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

2. Beware that, depending on the time range, your CSV file may contain entries for both `statistics` and `statistics_short_term` tables. You might want to ignore or remove data from the `statistics_short_term` if you're only interested in long-term statistics.

3. In Excel/spreadsheet software:
   - Identify missing time periods
   - Add new rows without IDs (leave ID field empty)
   - Set appropriate timestamps and values
   - Save the CSV

4. Preview and import the fixed data:
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
   - Remove the rows you don't want to migrate to the new sensor. This might include all data from the `statistics_short_term` table.
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

## 📝 Understanding the Recorder DB and CSV Format

For more details on the Home Assistant database schema, refer to the [official Home Assistant documentation](https://www.home-assistant.io/integrations/recorder/).

Home Assistant's database structure is key to effectively using this tool. The statistics-related tables store all sensor measurements for historical data and long-term trends.

Home Assistant might change the DB format from time to time. This documentation and the CLI itself is aware of the schema of the DB up to a certain number. If the schema changed in the meantime, a warning message will be displayed.

### Database Structure

The statistics data is primarily stored in three tables:

1. **statistics_meta**: Contains metadata about each entity
   - `id`: The primary key (metadata_id used in other tables)
   - `statistic_id`: The entity ID (e.g., `sensor.temperature_living_room`)
   - `unit_of_measurement`: The unit used for readings (e.g., °C, kWh)
   - `source`: The source of the statistics (usually "recorder")

2. **statistics**: Contains hourly aggregated data for long-term storage
   - `id`: The primary key for each record
   - `metadata_id`: References the entity in statistics_meta
   - `start_ts`: Unix timestamp for the start of the measurement period
   - `created_ts`: When the record was created
   - `mean`, `min`, `max`: Statistical values for the period
   - `sum`: Cumulative value (commonly used for energy, water consumption)
   - `state`: Last known state value
   - Other fields related to measurement characteristics

3. **statistics_short_term**: Contains 5-minute aggregated data for recent history
   - Same structure as the statistics table
   - Data typically gets purged after a configurable retention period

### Timestamps Explained

The database uses Unix timestamps (seconds since January 1, 1970):
- `start_ts`: Beginning of the measurement period
- `created_ts`: When the record was created (often slightly later than start_ts)
- `last_reset_ts`: For accumulating sensors (like energy), when the counter was last reset

When exporting data to CSV format, these timestamps are converted to human-readable dates in the format `YYYY-MM-DD HH:MM:SS`, and stored in the third column `date`. This field is provided only for human convenience and is ignored in the import process.

### CSV Format Details

When you export data, each row contains:

```
table,entity,date,id,metadata_id,created_ts,start_ts,mean,min,max,last_reset,last_reset_ts,state,sum
statistics,sensor.temperature_living_room,2025-05-17 12:00:00,1240825,342,1747238410.2970626,1747234800.0,21.5,21.0,22.0,,,,
[...]
```

Field definitions:
- `table`: Which table the record belongs to (`statistics` or `statistics_short_term`).
- `entity`: The entity ID (for information only, not used during import)
- `date`: Human-readable version of start_ts (for information only, not used during import)
- `id`: Database primary key (required for updates and deletes)
- `metadata_id`: References the entity definition in statistics_meta. This field is always required
- `created_ts`: When the record was created (Unix timestamp)
- `start_ts`: Start of the measurement period (Unix timestamp).
- `mean`: Average value during the period
- `min`: Minimum value during the period
- `max`: Maximum value during the period
- `last_reset`: Value at the last counter reset (for accumulating sensors)
- `last_reset_ts`: When the counter was last reset
- `state`: Last known state
- `sum`: Cumulative value (for accumulating sensors)

### Import Fields Requirements

When importing data:

1. **For updates** (modifying existing records):
   - `table`: Required to identify which table to update
   - `id`: Required to identify which record to update
   - Value fields you want to modify (`mean`, `min`, `max`, `state`, `sum`, etc.)

2. **For inserts** (adding new records):
   - `table`: Required
   - `metadata_id`: Required to identify which entity the data belongs to
   - `start_ts`: Required to specify when the measurement occurred
   - `created_ts`: Typically set to the same value as start_ts if not specified
   - Value fields for the new record

3. **For deletes** (removing records):
   - `table`: Required
   - `id`: Required to identify which record to delete
   - No value fields should be included

### Common Field Values by Sensor Type

Different types of sensors typically use different fields:

- **Regular sensors** (temperature, humidity, etc.):
  - Use `mean`, `min`, and `max` fields
  - `state` is sometimes populated
  - `sum` is usually empty

- **Accumulating sensors** (energy, water, etc.):
  - Use `sum` as the primary value
  - May have `last_reset` and `last_reset_ts` populated
  - `mean`, `min`, `max` might all be the same value

- **State sensors** (switches, modes):
  - Use `state` field
  - Other fields might be empty or populated with the same value

Understanding these fields helps you correctly modify data without introducing inconsistencies that might affect Home Assistant's functionality.

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
