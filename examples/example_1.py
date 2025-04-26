
import argparse
import logging
import sys
import time
from os import path as os_path

from src import pyfinbot

_logger = logging.getLogger(__name__)

MODULE_DIR = os_path.dirname(os_path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--instance", default="", help="instance name will be used to locate config (default: '')")
parser.add_argument("--config_path", default="", help="path to desired config (default: '')")
parser.add_argument("--logs_dir", default="", help="directory to desired logs (default: '')")


def close():
    _logger.info("Closing")
    time.sleep(2)
    sys.exit(f"Thanks for using {pyfinbot.version.PROJECT_NAME_TEXT}")


def main():
    args = parser.parse_args()
    instance: str = args.instance
    config_path: str = args.config_path
    logs_dir: str = args.logs_dir

    project_name = pyfinbot.version.PROJECT_NAME

    # Determine default config and logs paths if not provided
    if not config_path:
        config_filename = f"{project_name}{'' if not instance else '_' + instance}.conf"
        config_path = f"configs/{config_filename}"
    if not logs_dir:
        logs_instance_folder = f"{project_name}{'' if not instance else '_' + instance}"
        logs_dir = f"logs/{logs_instance_folder}"

    env = pyfinbot.loadEnv(config_path, project_dir=MODULE_DIR, instance=instance, logs_dir=logs_dir)
    _logger.info(f"Starting {pyfinbot.version.PROJECT_NAME_TEXT}.")

    try:
        conn, cur = pyfinbot.database.connect(env)
    except pyfinbot.DatabaseNotFoundError:
        pyfinbot.database.createDatabase(env, 1)
        conn, cur = pyfinbot.database.connect(env)
    finally:
        close()


if __name__ == "__main__":
    main()
