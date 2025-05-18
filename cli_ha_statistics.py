#!/usr/bin/env python3
"""
Home Assistant Sensor Data CLI (Single-file Version)

A command-line interface for managing Home Assistant sensor data, addressing gaps in the 
built-in data management capabilities. This tool helps with data exploration, analysis,
modification, and migration tasks.

Install Instructions:
---------------------
1. Create and activate a virtual environment:
   python3 -m venv venv
   source venv/bin/activate

2. Install dependencies:
   pip install click sqlalchemy tabulate

3. Run the CLI:
   python cli_ha_statistics.py [COMMAND] [OPTIONS]

Available commands:
  - status: Summarize DB tables and storage usage
  - list: List entities with metadata and statistics
  - export: Export records to CSV with filtering options
  - import: Import records from CSV with dry-run capability
"""

import sys
import logging
import csv
from datetime import datetime, timezone

import click
from sqlalchemy import create_engine, MetaData, select, func, literal, text
from tabulate import tabulate

# Constants
BYTES_PER_FIELD = 8  # Estimated bytes per database field for size calculations
DEFAULT_DB_URL = 'sqlite:///home-assistant_v2.db'
KNOWN_SCHEMA_VERSION = 50  # Known compatible schema version

# Logging setup
def setup_logging(level=logging.INFO):
    """Configure logging with consistent format."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger('ha_data_cli')

logger = setup_logging()

def ts_to_datetime(timestamp):
    """Convert Unix timestamp to datetime with timezone info."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)

@click.group()
@click.option('--db-url', envvar='HA_DB_URL', default=DEFAULT_DB_URL,
              help='SQLAlchemy DB URL for Home Assistant recorder DB')
@click.pass_context
def cli(ctx, db_url):
    """Initialize DB engine and metadata."""
    ctx.ensure_object(dict)
    
    # Connect to database
    try:
        engine = create_engine(db_url)
        engine.connect().close()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)
        
    # Reflect database structure
    meta = MetaData()
    meta.reflect(bind=engine)
    ctx.obj['ENGINE'] = engine
    ctx.obj['META'] = meta
    
    # Check schema version
    schema_tbl = meta.tables.get('schema_changes')
    if schema_tbl is not None:
        with engine.connect() as conn:
            ver = conn.execute(
                select(schema_tbl.c.schema_version).order_by(schema_tbl.c.change_id.desc())
            ).scalar()
        ctx.obj['SCHEMA_VERSION'] = ver
        if ver > KNOWN_SCHEMA_VERSION:
            click.echo(f"WARNING: Detected schema version {ver} > {KNOWN_SCHEMA_VERSION}")
            click.echo("This may indicate compatibility issues. Proceed with caution.")

@cli.command()
@click.pass_context
def status(ctx):
    """Summarize DB tables: rows, cols, records, percent, megabytes"""
    engine = ctx.obj['ENGINE']
    meta = ctx.obj['META']
    dialect = engine.dialect.name
    schema = ctx.obj.get('SCHEMA_VERSION', 'unknown')
    
    # Print database information
    click.echo(f"Database type: {dialect}, schema {schema}")
    click.echo(f"Time: {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    click.echo("-" * 70)

    # Collect table statistics
    total_records = total_bytes = 0
    table_data = []
    
    with engine.connect() as conn:
        for tbl in meta.sorted_tables:
            rows = conn.execute(select(func.count()).select_from(tbl)).scalar() or 0
            cols = len(tbl.columns)
            recs = rows * cols
            size_b = recs * BYTES_PER_FIELD
            total_records += recs
            total_bytes += size_b
            table_data.append((tbl.name, rows, cols, recs, size_b))
    
    # Format and display results
    headers = ['Table', 'Rows', 'Cols', 'Records', '% total', '~ MB']
    rows_out = []
    
    for name, r, c, recs, b in table_data:
        pct = recs/total_records*100 if total_records else 0
        mb = b / (1024 ** 2)
        rows_out.append([name, r, c, recs, f"{pct:.1f}%", f"{mb:.1f}"])
    
    click.echo(tabulate(rows_out, headers=headers, tablefmt='plain'))
    click.echo("-" * 70)
    click.echo(f"TOTAL RECORDS: {total_records:,}")
    click.echo(f"TOTAL SIZE: {total_bytes/(1024**2):.2f} MB")


@cli.command()
@click.option('--sort', type=click.Choice(['count', 'first', 'last', 'kb']), default=None,
              help='Sort results by this column')
@click.option('--reverse', is_flag=True, help='Reverse sort order')
@click.option('--csv', 'csv_mode', is_flag=True, help='Output in CSV format')
@click.option('--after', type=click.DateTime(), help='Only consider data after this date')
@click.option('--before', type=click.DateTime(), help='Only consider data before this date')
@click.pass_context
def list(ctx, sort, reverse, csv_mode, after, before):
    """List entities with count, first/last seen, KB, unit."""
    engine = ctx.obj['ENGINE']
    meta = ctx.obj['META']
    
    # Get required tables
    stats = meta.tables.get('statistics')
    stats_short = meta.tables.get('statistics_short_term')
    meta_tbl = meta.tables.get('statistics_meta')
    
    if stats is None or stats_short is None or meta_tbl is None:
        click.echo("Missing required statistics tables.")
        return

    # Process date filters if provided
    start_ts = after.timestamp() if after else None
    end_ts = before.timestamp() if before else None

    def collect(table):
        """Build query to collect stats from a table."""
        stmt = select(table.c.metadata_id,
                      func.min(table.c.start_ts).label('first'),
                      func.max(table.c.start_ts).label('last'),
                      func.count().label('count'))
        stmt = stmt.group_by(table.c.metadata_id)
        
        # Apply date filters if specified
        if start_ts: 
            stmt = stmt.where(table.c.start_ts >= start_ts)
        if end_ts: 
            stmt = stmt.where(table.c.start_ts <= end_ts)
            
        return stmt

    # Aggregate statistics from both tables
    agg = {}
    with engine.connect() as conn:
        # Collect data from both statistics tables
        for tbl in (stats, stats_short):
            for row in conn.execute(collect(tbl)):
                mid = row.metadata_id
                rec = agg.setdefault(mid, {'count': 0, 'first': row.first, 'last': row.last})
                rec['count'] += row.count
                rec['first'] = min(rec['first'], row.first)
                rec['last'] = max(rec['last'], row.last)

        # Look up metadata for each entity
        results = []
        cols = len(stats.columns)
        
        for mid, data in agg.items():
            # Get entity ID and unit of measurement
            eid = conn.execute(
                select(meta_tbl.c.statistic_id).where(meta_tbl.c.id == mid)
            ).scalar() or ''
            
            unit = conn.execute(
                select(meta_tbl.c.unit_of_measurement).where(meta_tbl.c.id == mid)
            ).scalar() or ''
            
            # Calculate storage size
            cnt = data['count']
            kb = round(cnt * cols * BYTES_PER_FIELD / 1024, 1)
            
            # Format timestamps as datetime objects
            first_dt = ts_to_datetime(data['first']).replace(microsecond=0)
            last_dt = ts_to_datetime(data['last']).replace(microsecond=0)

            # Format when displaying
            formatted_first = first_dt.strftime('%Y-%m-%d %H:%M:%S')
            formatted_last = last_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Add to results
            results.append({
                'entity': eid,
                'count': cnt,
                'first': formatted_first,
                'last': formatted_last,
                'kb': kb,
                'unit': unit
            })
    
    # Sort results if requested
    if sort: 
        results.sort(key=lambda x: x[sort], reverse=reverse)
    
    # Prepare output
    headers = ['Entity', 'Count', 'First', 'Last', '~ KB', 'Unit']
    
    if csv_mode:
        # CSV output
        w = csv.writer(sys.stdout)
        w.writerow(headers)
        for e in results: 
            w.writerow([e[h.lower()] for h in headers])
    else:
        # Table output
        table_out = [
            [e['entity'], e['count'], e['first'], e['last'], e['kb'], e['unit']] 
            for e in results
        ]
        click.echo(tabulate(table_out, headers=headers, tablefmt='plain'))


@cli.command()
@click.argument('entities', nargs=-1)
@click.option('--above', type=float, help='Only include values above this threshold')
@click.option('--below', type=float, help='Only include values below this threshold')
@click.option('--after', type=click.DateTime(), help='Only include data after this date')
@click.option('--before', type=click.DateTime(), help='Only include data before this date')
@click.pass_context
def export(ctx, entities, above, below, after, before):
    """Export CSV rows with all fields, entity, and human date."""
    engine = ctx.obj['ENGINE']
    meta = ctx.obj['META']
    
    # Get required tables
    stats = meta.tables['statistics']
    stats_short = meta.tables['statistics_short_term']
    meta_tbl = meta.tables['statistics_meta']
    
    # Get column names for later use
    cols = [c.name for c in stats.columns]
    
    # Setup CSV writer
    writer = csv.writer(sys.stdout)
    writer.writerow(['table', 'entity (ignored)', 'date (ignored)'] + cols)

    # Convert date parameters to timestamps if provided
    after_ts = after.timestamp() if after else None
    before_ts = before.timestamp() if before else None
    
    # Process each entity
    with engine.connect() as conn:
        for ent in entities:
            # Find metadata_id for this entity
            mid = conn.execute(
                select(meta_tbl.c.id).where(meta_tbl.c.statistic_id == ent)
            ).scalar()
            
            if mid is None:
                click.echo(f"Warning: Entity '{ent}' not found", err=True)
                continue
                
            # Query both tables for this entity
            for tbl in (stats, stats_short):
                # Build query with all columns
                q = select(literal(tbl.name).label('table'), *[tbl.c[c] for c in cols])
                q = q.where(tbl.c.metadata_id == mid)
                
                # Apply date range filters if provided
                if after_ts:
                    q = q.where(tbl.c.start_ts >= after_ts)
                if before_ts:
                    q = q.where(tbl.c.start_ts <= before_ts)
                    
                # Apply value thresholds if provided
                # Match if ANY of mean, min, or max values fall within bounds
                if above is not None and below is not None:
                    # Between above (exclusive) and below (exclusive)
                    q = q.where(
                        (tbl.c.mean > above) & (tbl.c.mean < below) |
                        (tbl.c.min > above) & (tbl.c.min < below) |
                        (tbl.c.max > above) & (tbl.c.max < below)
                    )
                elif above is not None:
                    # Any value strictly above threshold
                    q = q.where((tbl.c.mean > above) | (tbl.c.min > above) | (tbl.c.max > above))
                elif below is not None:
                    # Any value strictly below threshold
                    q = q.where((tbl.c.mean < below) | (tbl.c.min < below) | (tbl.c.max < below))
                
                # Process and output results
                for r in conn.execute(q).mappings():
                    ts = r['start_ts']
                    # Format timestamps as datetime objects
                    date_ts = ts_to_datetime(ts).replace(microsecond=0)
                    formatted_date = date_ts.strftime('%Y-%m-%d %H:%M:%S')
                    # Create output row
                    row = [r['table'], ent, formatted_date] + [r[c] for c in cols]
                    writer.writerow(row)

@cli.command(name='import')
@click.argument('csv_file', type=click.File('r'))
@click.option('--dry-run', is_flag=True, help='Print the rows that would be imported without modifying the database.')
@click.pass_context
def import_cmd(ctx, csv_file, dry_run):
    """Import CSV, generate or execute SQL for changes only."""
    engine = ctx.obj['ENGINE']
    meta = ctx.obj['META']
    stats = meta.tables['statistics']
    stats_short = meta.tables['statistics_short_term']
    tables = {'statistics': stats, 'statistics_short_term': stats_short}
    changes = {'insert': 0, 'delete': 0, 'update': 0, 'skip': 0}
    operations = []

    if dry_run:
        click.echo("=== DRY RUN MODE: SQL commands that would be executed ===")
        click.echo("=" * 75)

    try:
        # Read CSV rows and validate column count
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames or []
        expected = len(fieldnames)
        rows = []
        for idx, row in enumerate(reader, start=2):
            if len(row) != expected:
                click.echo(f"CSV structure error at line {idx}: expected {expected} columns, got {len(row)}")
                return
            rows.append(row)
    except Exception as e:
        click.echo(f"Error reading CSV file: {e}")
        return

    for row in rows:
        try:
            tbl_name = row.get('table')
            if tbl_name not in tables:
                click.echo(f"Skipping row with invalid table: {tbl_name}")
                continue
            tbl = tables[tbl_name]
            data = {}
            for col in tbl.c.keys():
                val = row.get(col, '').strip()
                if not val:
                    continue
                try:
                    data[col] = int(val) if col in ('id', 'metadata_id') else float(val)
                except ValueError:
                    click.echo(f"Warning: Could not convert {col}={val}, skipping")
            record_id = data.get('id')
            metadata_cols = {'id','table','entity','date','metadata_id','created_ts','start_ts'}
            data_cols = set(data.keys()) - metadata_cols

            # Delete operation
            if record_id and not data_cols:
                operations.append(f"DELETE FROM {tbl_name} WHERE id = {record_id};")
                changes['delete'] += 1
                continue
            # Insert operation
            if not record_id:
                if 'metadata_id' not in data or 'start_ts' not in data:
                    click.echo("Warning: missing metadata_id or start_ts for insert, skipping")
                    continue
                data.setdefault('created_ts', data['start_ts'])
                cols_str = ', '.join(data.keys())
                vals_str = ', '.join(str(v) if isinstance(v, int) else f"{v:.6f}" for v in data.values())
                operations.append(f"INSERT INTO {tbl_name} ({cols_str}) VALUES ({vals_str});")
                changes['insert'] += 1
                continue
            # Update operation
            if record_id and data_cols:
                with engine.connect() as conn:
                    cur = conn.execute(select(tbl).where(tbl.c.id == record_id)).fetchone()
                if not cur:
                    cols_str = ', '.join(data.keys())
                    vals_str = ', '.join(str(v) if isinstance(v, int) else f"{v:.6f}" for v in data.values())
                    operations.append(f"INSERT INTO {tbl_name} ({cols_str}) VALUES ({vals_str});")
                    changes['insert'] += 1
                else:
                    set_parts = []
                    for col in data_cols:
                        new = data[col]
                        old = getattr(cur, col)
                        if abs(float(old) - float(new)) > 1e-6:
                            val_str = str(new) if isinstance(new, int) else f"{new:.6f}"
                            set_parts.append(f"{col} = {val_str}")
                    if set_parts:
                        operations.append(f"UPDATE {tbl_name} SET {', '.join(set_parts)} WHERE id = {record_id};")
                        changes['update'] += 1
                    else:
                        changes['skip'] += 1
        except Exception as e:
            click.echo(f"Error processing row: {e}")

    if dry_run:
        click.echo(f"Operations summary: {changes['insert']} inserts, {changes['update']} updates, {changes['delete']} deletes, {changes['skip']} skips")
        click.echo("SQL to execute:")
        for op in operations:
            click.echo(op)
        click.echo("Dry run complete, no changes applied.")
        return

    # Execute SQL operations
    with engine.begin() as conn:
        for op in operations:
            try:
                conn.execute(text(op))
            except Exception as e:
                click.echo(f"Error executing {op}: {e}")
    click.echo(f"Import done: {changes['insert']} inserts, {changes['update']} updates, {changes['delete']} deletes, {changes['skip']} skips")

if __name__ == '__main__':
    cli()
