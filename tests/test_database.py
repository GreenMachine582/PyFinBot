import unittest
from os import path as os_path
from unittest.mock import patch, MagicMock, mock_open, call

from src.pyfinbot import DatabaseError
from src.pyfinbot.tools.database import (createDatabase, upgradeDatabase, getLatestAvailableVersion,
                                           applySchemaVersion, runDataPopulationScript, _connect, connect,
                                           getSchemaVersion)

class TestDatabaseFunctions(unittest.TestCase):

    def setUp(self):
        """Set up environment and mock configuration."""
        self.env = MagicMock()
        self.env.config = {
            "database": {
                "dbname": "test_db",
                "user": "test_user",
                "password": "test_pass",
                "host": "localhost",
                "port": "5432"
            }
        }
        self.env.PROJECT_DIR = os_path.abspath("/mock/project")
        self.env.conn = MagicMock()
        self.env.cur = MagicMock()

    @patch('os.listdir', return_value=['v1_create_schema.sql', 'v2_create_schema.sql'])
    def test_get_latest_version(self, mock_listdir):
        """Test getLatestAvailableVersion correctly identifies the latest version."""
        database_dir = '/mock/project/database'
        latest_version = getLatestAvailableVersion(database_dir)
        self.assertEqual(latest_version, 2)

    @patch('builtins.open', new_callable=mock_open, read_data="SQL COMMAND")
    def test_apply_schema_version_create(self, mock_file):
        """Test applySchemaVersion for creating a schema."""
        applySchemaVersion(os_path.abspath('/mock/project/database'), self.env.cur, 0, 1)
        self.assertEqual(self.env.cur.execute.call_count, 2)
        self.env.cur.execute.assert_any_call("SQL COMMAND")
        self.env.cur.execute.assert_any_call(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")

        mock_file.assert_called_with(os_path.abspath('/mock/project/database/v1_create_schema.sql'), 'r')

    @patch('builtins.open', new_callable=mock_open, read_data="SQL UPGRADE COMMAND")
    def test_apply_schema_version_upgrade(self, mock_file):
        """Test applySchemaVersion for upgrading schema."""
        applySchemaVersion(os_path.abspath('/mock/project/database'), self.env.cur, 1, 2)
        self.assertEqual(self.env.cur.execute.call_count, 2)
        self.env.cur.execute.assert_any_call("SQL UPGRADE COMMAND")
        self.env.cur.execute.assert_any_call(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")

        mock_file.assert_called_with(os_path.abspath('/mock/project/database/v1_to_v2_upgrade_schema.sql'), 'r')

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data="def populate(env): env.cur.execute('INSERT INTO table')")
    def test_run_data_population_script_create(self, mock_file, mock_exists):
        """Test runDataPopulationScript for creating population."""
        result = runDataPopulationScript(os_path.abspath('/mock/project/database'), 0, 1, self.env)
        self.env.cur.execute.assert_has_calls([call("BEGIN"), call("INSERT INTO table"), call("COMMIT")])
        mock_file.assert_called_with(os_path.abspath('/mock/project/database/v1_create_populate.py'), 'r')
        self.assertTrue(result)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data="def populate(env): env.cur.execute('UPDATE table')")
    def test_run_data_population_script_upgrade(self, mock_file, mock_exists):
        """Test runDataPopulationScript for upgrading population."""
        result = runDataPopulationScript(os_path.abspath('/mock/project/database'), 1, 2, self.env)
        self.env.cur.execute.assert_has_calls([call("BEGIN"), call("UPDATE table"), call("COMMIT")])
        mock_file.assert_called_with(os_path.abspath('/mock/project/database/v1_to_v2_upgrade_populate.py'), 'r')
        self.assertTrue(result)

    @patch('os.path.exists', return_value=False)
    def test_run_data_population_script_no_file(self, mock_exists):
        """Test runDataPopulationScript where no population script exists."""
        result = runDataPopulationScript(os_path.abspath('/mock/project/database'), 1, 2, self.env)
        self.assertFalse(result)

    @patch('src.pyfinbot.tools.database._connect')
    @patch('src.pyfinbot.tools.database.getLatestAvailableVersion', return_value=2)
    @patch('src.pyfinbot.tools.database.applySchemaVersion')
    @patch('src.pyfinbot.tools.database.runDataPopulationScript')
    def test_create_database(self, mock_run_data, mock_apply_schema, mock_latest_version, mock_connect):
        """Test createDatabase function."""
        mock_connect.return_value = (self.env.conn, self.env.cur)

        createDatabase(self.env)

        mock_connect.assert_called()
        mock_apply_schema.assert_called_with(os_path.join(os_path.abspath('/mock/project/database'), ''), self.env.cur, 0, 2)
        mock_run_data.assert_called_with(os_path.join(os_path.abspath('/mock/project/database/'), ''), 0, 2, self.env)

    @patch('src.pyfinbot.tools.database._connect')
    @patch('src.pyfinbot.tools.database.getLatestAvailableVersion', return_value=2)
    @patch('src.pyfinbot.tools.database.applySchemaVersion')
    @patch('src.pyfinbot.tools.database.runDataPopulationScript')
    @patch('src.pyfinbot.tools.database.dropDatabase')
    def test_create_database_failure_triggers_drop(self, mock_drop_db, mock_run_data, mock_apply_schema,
                                                   mock_latest_version, mock_connect):
        """Test that the database is dropped if schema application fails."""
        # Setup: Mock connection and cursor
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = (mock_conn, mock_cur)

        # Simulate schema application failure
        mock_apply_schema.side_effect = Exception("Simulated schema error")

        with self.assertRaises(DatabaseError):
            createDatabase(self.env)

        # Verify that rollback and close were called
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called()  # Should have two, one for rollback and one for db drop conn

        # Ensure dropDatabase was called with correct parameters
        mock_drop_db.assert_called_once_with(self.env.config["database"])

    @patch('src.pyfinbot.tools.database._connect')
    @patch('src.pyfinbot.tools.database.applySchemaVersion')
    @patch('src.pyfinbot.tools.database.runDataPopulationScript')
    def test_upgrade_database(self, mock_run_data, mock_apply_schema, mock_connect):
        """Test upgradeDatabase function."""
        mock_connect.return_value = (self.env.conn, self.env.cur)

        upgradeDatabase(self.env, from_version=1, to_version=2)

        mock_connect.assert_called()
        mock_apply_schema.assert_called_with(os_path.join(os_path.abspath('/mock/project/database/'), ''), self.env.cur, 1, 2)
        mock_run_data.assert_called_with(os_path.join(os_path.abspath('/mock/project/database/'), ''), 1, 2, self.env)


class TestDatabaseGetSchemaVersion(unittest.TestCase):

    def setUp(self):
        """Set up a mock cursor for database interactions."""
        self.cur = MagicMock()

    def test_get_schema_version_success(self):
        """Test getSchemaVersion when the version exists."""
        # Mock the cursor's fetchone method to return a valid version
        self.cur.fetchone.return_value = (1,)

        # Call the function and assert the correct version is returned
        result = getSchemaVersion(self.cur)
        self.assertEqual(result, 1)
        self.cur.execute.assert_called_once_with("""
            SELECT version
            FROM schema_version
            ORDER BY applied_at DESC
            LIMIT 1;
        """)

    def test_get_schema_version_no_version(self):
        """Test getSchemaVersion when no version is found in the table."""
        # Mock the cursor's fetchone method to return None (no version found)
        self.cur.fetchone.return_value = None

        # Call the function and assert that None is returned
        result = getSchemaVersion(self.cur)
        self.assertIsNone(result)
        self.cur.execute.assert_called_once_with("""
            SELECT version
            FROM schema_version
            ORDER BY applied_at DESC
            LIMIT 1;
        """)

    def test_get_schema_version_error(self):
        """Test getSchemaVersion when an error occurs during query execution."""
        # Mock the cursor's execute method to raise an exception
        self.cur.execute.side_effect = Exception("Database error")

        # Ensure the function raises a DatabaseError
        with self.assertRaises(DatabaseError):
            getSchemaVersion(self.cur)

        # Assert that the execute method was called once before the error
        self.cur.execute.assert_called_once_with("""
            SELECT version
            FROM schema_version
            ORDER BY applied_at DESC
            LIMIT 1;
        """)


if __name__ == '__main__':
    unittest.main()
