import logging
import os
import re
import traceback
from datetime import datetime
from os import path as os_path

import psycopg2

_logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base class for other database-related exceptions."""
    pass

class DatabaseNotFoundError(DatabaseError):
    """Raised when the database does not exist."""
    pass

class SchemaFileNotFoundError(DatabaseError):
    """Raised when the schema file is not found."""
    pass

class SchemaApplicationError(DatabaseError):
    """Raised when an error occurs while applying the schema."""
    pass

class DataPopulationError(DatabaseError):
    """Raised when an error occurs while populating data."""
    pass


def _connect(env=None, autocommit: bool = True, **params) -> tuple:
    """ Establish a connection to the PostgreSQL database and return the connection and cursor objects. """
    conn = psycopg2.connect(**params)
    conn.autocommit = autocommit
    cur = conn.cursor()
    if env is not None:
        env.conn = conn
        env.cur = cur
    return conn, cur


def enforceSchemaVersion(cur, database_schema_dir: str = "", version: int = -1):
    """ Enforce the current database schema version matches the target version. """
    assert version and isinstance(version, int), "version must be an integer starting from 1 or -1 for latest version."
    db_version = getSchemaVersion(cur)
    if version == -1:
        if not database_schema_dir:
            raise ValueError("database_schema_dir must be provided for latest version.")
        version = getLatestAvailableVersion(database_schema_dir)  # DB version is latest available version
    if db_version != version:
        raise DatabaseError(f"DB version is {db_version}, however the target version is "
                            f"{version}.")


def connect(env, enforce_version: int = None, **kwargs) -> tuple:
    """ Connect to the project database server. """
    params = env.config["database"].copy()
    params.update(kwargs)
    _logger.info(f"Connecting to the {env.project_name_text} database...")

    try:
        (conn, cur) = _connect(env, **params)
        if enforce_version:
            enforceSchemaVersion(cur, os_path.join(env.PROJECT_DIR, "database", ""), enforce_version)
        return conn, cur
    except psycopg2.OperationalError as db_error:
        if f'database "{params.get("dbname")}" does not exist' in db_error.args[0]:
            _logger.error(f"Database does not exist or is inaccessible: {db_error}")
            raise DatabaseNotFoundError("Database does not exist. Please create the database before proceeding.")
        raise DatabaseError(f"Operational error occurred: {db_error}")
    except (Exception, psycopg2.DatabaseError) as error:
        _logger.error(f"Error: {error}")
        raise DatabaseError(f"An error occurred: {error}")


def getLatestAvailableVersion(database_dir: str):
    """ Get the latest version of the schema. """
    files = os.listdir(database_dir)

    # Extract version numbers from filenames
    versions = []
    for f in files:
        match = re.match(r'v(\d+)_create_schema\.sql', f)
        if match:
            versions.append(int(match.group(1)))

    if not versions:
        raise ValueError("No valid schema files found.")
    return max(versions)


def injectAuditColumns(cursor):
    """Inject standard audit columns into all applicable tables if they are missing."""
    audit_columns = {
        'create_datetime': "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL",
        'write_datetime': "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL",
        'create_uid': "INTEGER REFERENCES users(id)",
        'write_uid': "INTEGER REFERENCES users(id)"
    }

    # Get all user tables except versioning
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    table_names = {row[0] for row in cursor.fetchall()} - {'schema_version'}

    for table in table_names:
        for column, definition in audit_columns.items():
            cursor.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
            """, (table, column))
            if not cursor.fetchone():
                _logger.debug(f"Adding missing column '{column}' to table '{table}'...")
                cursor.execute(f"""
                    ALTER TABLE {table}
                    ADD COLUMN {column} {definition}
                """)


def applySchemaVersion(database_dir: str, cursor, from_version: int, to_version: int):
    """Apply the schema for the specified version, handling both create and upgrade scenarios."""
    method = "upgrade" if from_version else "create"
    version_text = f"v{from_version} to v{to_version}" if from_version else f"v{to_version}"

    if not from_version:  # Creation case
        schema_file = os_path.join(database_dir, f"v{to_version}_create_schema.sql")
    else:  # Upgrade case
        schema_file = os_path.join(database_dir, f"v{from_version}_to_v{to_version}_upgrade_schema.sql")

    _logger.debug(f"Applying {method} schema for {version_text}...")

    try:
        with open(schema_file, 'r') as file:
            cursor.execute(file.read())
        _logger.debug(f"{method.capitalize()} schema for {version_text} applied successfully.")

        # Inject create/write datetime columns if missing
        injectAuditColumns(cursor)
    except FileNotFoundError:
        _logger.error(f"{method.capitalize()}  schema file {schema_file} not found.")
        raise SchemaFileNotFoundError(f"Schema file {schema_file} not found.")
    except (Exception, psycopg2.DatabaseError) as error:
        _logger.error(f"Error applying {method} schema for {version_text}: {error}")
        raise SchemaApplicationError(f"Error applying {method} schema for {version_text}: {error}")


def runDataPopulationScript(database_dir: str, from_version: int, to_version: int, env) -> bool:
    """Look for and run a Python script to populate or upgrade the database."""
    method = "upgrade" if from_version else "create"
    version_text = f"v{from_version} to v{to_version}" if from_version else f"v{to_version}"

    if not from_version:  # Creation case
        script_file = os_path.join(database_dir, f"v{to_version}_create_populate.py")
    else:  # Upgrade case
        script_file = os_path.join(database_dir, f"v{from_version}_to_v{to_version}_upgrade_populate.py")

    if not os_path.exists(script_file):
        _logger.debug(f"No {method} population script found for {version_text}.")
        return False

    _logger.debug(f"Starting transaction for {method} population script for {version_text}...")

    try:
        env.cur.execute("BEGIN")  # Start a transaction

        _logger.debug(f"Running data population script: {script_file}")
        script_namespace = {}
        with open(script_file, 'r') as file:
            try:
                exec(file.read(), script_namespace)
            except ModuleNotFoundError as e:
                _logger.error(f"Module import error in {script_file}: {e}")
                raise DataPopulationError(f"Missing module: {e}")
            except Exception as e:
                _logger.error(f"Error executing the script {script_file}: {e}")
                raise

        if 'populate' in script_namespace:
            try:
                script_namespace['populate'](env)
                _logger.debug("Data population script executed successfully.")
            except Exception as e:
                _logger.error(f"Error while executing 'populate' function in {script_file}: {e}")
                _logger.debug(traceback.format_exc())
                raise DataPopulationError(f"Error in 'populate' function: {e}")
        else:
            _logger.warning(f"No 'populate' function found in {script_file}.")

        env.cur.execute("COMMIT")  # Commit the transaction if everything goes well
        _logger.debug("Transaction committed successfully.")
        return True

    except Exception as e:
        _logger.error(f"Error during data population: {e}")
        env.cur.execute("ROLLBACK")  # Rollback the entire transaction
        raise DataPopulationError("An error occurred during data population. Transaction rolled back.")


def dropDatabase(params: dict):
    db_name = params.get('dbname')
    _logger.warning(f"Attempting to drop database '{db_name}' due to failure...")

    try:
        # Connect with autocommit set immediately
        drop_conn = psycopg2.connect(
            dbname='postgres',
            user=params.get('user'),
            host=params.get('host'),
            port=params.get('port'),
            password=params.get('password'),
        )
        drop_conn.set_session(autocommit=True)

        with drop_conn.cursor() as drop_cur:
            drop_cur.execute(f"DROP DATABASE IF EXISTS {db_name}")
            _logger.info(f"Database '{db_name}' dropped successfully.")

        drop_conn.close()
    except Exception as drop_error:
        _logger.error(f"Failed to drop database '{db_name}': {drop_error}")


def createDatabase(env, version: int = None):
    """Create the database from the newest or specified version with proper locking."""
    params = env.config["database"]
    db_name = params.get("dbname")
    _logger.info(f"Creating database {db_name} from v{version}...")

    database_dir = os_path.join(env.PROJECT_DIR, "database", "")
    conn = None

    try:
        # Connect to the default PostgreSQL database to create the project database
        default_params = params.copy()
        default_params['dbname'] = 'postgres'  # Use the default 'postgres' db to create the new database
        conn, cur = _connect(env, **default_params)

        # Check if the database already exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", [db_name])
        exists = cur.fetchone()
        if exists:
            _logger.debug(f"Database {db_name} already exists. Proceeding with schema creation.")
        else:
            cur.execute(f"CREATE DATABASE {db_name}")
            _logger.debug(f"Database {db_name} created successfully.")

        cur.close()
        conn.close()

        # Reconnect to the newly created database to apply the schema
        params['dbname'] = db_name
        conn, cur = _connect(env, autocommit=False, **params)

        if version is None:
            version = getLatestAvailableVersion(database_dir)

        # Apply the schema for the specified version
        applySchemaVersion(database_dir, cur, 0, version)

        # Start a transaction and acquire an exclusive lock on the schema_version table
        cur.execute("BEGIN")
        cur.execute("LOCK TABLE schema_version IN ACCESS EXCLUSIVE MODE")
        _logger.debug("Acquired exclusive lock on schema_version table.")

        # Run data population script if available
        script_applied = runDataPopulationScript(database_dir, 0, version, env)

        # Commit the transaction
        conn.commit()
        _logger.info(f"Database {db_name} created"
                     f"{', schema and population script' if script_applied else ' and schema'} v{version} applied.")
        _logger.debug("Transaction committed successfully.")

    except DatabaseError as db_error:
        _logger.error(f"Database creation failed: {db_error}")
        if conn:
            conn.rollback()  # Rollback if an error occurs
            _logger.debug("Transaction rolled back due to error.")
        dropDatabase(params)
        raise
    except (Exception, psycopg2.DatabaseError) as error:
        _logger.error(f"Error: {error}")
        if conn:
            conn.rollback()  # Rollback on generic error
        dropDatabase(params)

        raise DatabaseError(f"An error occurred: {error}")
    finally:
        if conn is not None:
            conn.close()  # Close the connection
            _logger.debug(f"Database connection closed.")


def upgradeDatabase(env, from_version: int, to_version: int):
    """Upgrade the database schema from a specific version to a target version with proper locking."""
    params = env.config["database"]
    db_name = params.get("dbname")
    _logger.info(f"Upgrading database {db_name} from version {from_version} to {to_version}...")

    database_dir = os_path.join(env.PROJECT_DIR, "database", "")
    conn, cur = None, None

    try:
        # Connect to the database to apply upgrades
        conn, cur = _connect(env, autocommit=False, **params)

        # Start a transaction and acquire an exclusive lock on the schema_version table
        cur.execute("BEGIN")
        cur.execute("LOCK TABLE schema_version IN ACCESS EXCLUSIVE MODE")
        _logger.debug("Acquired exclusive lock on schema_version table.")

        # Apply schema updates from the current version to the target version
        for version in range(from_version, to_version):
            _logger.debug(f"Applying schema update for version {version}...")
            # Apply schema update
            applySchemaVersion(database_dir, cur, version, version + 1)

            # Run data population script if available
            runDataPopulationScript(database_dir, version, version + 1, env)

        # Update schema_version table with the new version
        cur.execute("""
            INSERT INTO schema_version (version, description) 
            VALUES (%s, %s) 
            ON CONFLICT (version) DO NOTHING
            """, (to_version, f'Upgraded to schema version {to_version}')
        )

        # Commit the transaction
        conn.commit()
        _logger.info(f"Database upgraded to schema version {to_version}.")
        _logger.debug("Transaction committed successfully.")

    except Exception as e:
        _logger.error(f"Error during database upgrade: {e}")
        if conn and cur:
            conn.rollback()  # Rollback the transaction on error
            _logger.debug("Transaction rolled back due to error.")
        raise DatabaseError("An error occurred during database upgrade. Transaction rolled back.")
    finally:
        if conn is not None:
            conn.close()  # Ensure the connection is closed
            _logger.debug("Database connection closed.")


def getSchemaVersion(cur):
    """Fetch the current database schema version."""
    try:
        # Query the latest version from the schema_version table
        cur.execute("""
            SELECT version
            FROM schema_version
            ORDER BY applied_at DESC
            LIMIT 1;
        """)

        # Fetch the result
        version_record = cur.fetchone()

        if version_record is None:
            # If no version is found, the database is un-versioned
            _logger.warning("No version record found. The database might not be initialised.")
            return None
        return version_record[0]
    except Exception as e:
        _logger.error(f"Error while fetching the database version: {e}")
        raise DatabaseError("Failed to get database version.")


def insertRecord(cursor, table_name: str, data: dict, user_id: int = None) -> int:
    """Generic insert into a table, automatically handling audit fields."""
    fields = list(data.keys())
    values = list(data.values())

    # Add audit fields
    fields += ['create_datetime', 'write_datetime']
    values += [datetime.now(), datetime.now()]

    if user_id is not None:
        fields += ['create_uid', 'write_uid']
        values += [user_id, user_id]

    placeholders = ', '.join(['%s'] * len(values))
    columns = ', '.join(fields)

    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) RETURNING id;"
    cursor.execute(sql, values)

    return cursor.fetchone()[0]


def updateRecord(cursor, table_name: str, record_id: int, data: dict, user_id: int = None):
    """Generic update to a table, automatically handling audit fields."""
    fields = list(data.keys())
    values = list(data.values())

    # Always update write_datetime
    fields.append('write_datetime')
    values.append(datetime.now())

    if user_id is not None:
        fields.append('write_uid')
        values.append(user_id)

    set_clause = ', '.join([f"{field} = %s" for field in fields])

    sql = f"UPDATE {table_name} SET {set_clause} WHERE id = %s;"
    values.append(record_id)

    cursor.execute(sql, values)

