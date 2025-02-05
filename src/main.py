import requests
import json
import os
import sys
import time
import re
from copy import deepcopy
from enum import Enum
from jsonmerge import merge
import logging, logging.config

from core_client import Client
from core_client.base.models.v3 import (
    ProcessConfig,
    ProcessConfigLimit,
    ProcessConfigIO,
    ProcessConfigIOCleanup
)
from core_client.base.models import Error

# Local
# from dotenv import load_dotenv
# load_dotenv()

CORE_ADDRESS = os.getenv('CORE_ADDRESS', '')
CORE_USERNAME = os.getenv('CORE_USERNAME', '')
CORE_PASSWORD = os.getenv('CORE_PASSWORD', '')
FILESYSTEMS = os.getenv('FILESYSTEMS', 'memfs')

PROCESS_REFERENCE = os.getenv('PROCESS_REFERENCE', 'rtmp:hls')
SYNC_INTERVAL_SECONDS = int(os.getenv('SYNC_INTERVAL_SECONDS', 10))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

BASE_PATH = os.path.realpath(os.path.dirname(__file__))
LOG_FILE = os.path.join(BASE_PATH, 'console.log')

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            'stream': 'ext://sys.stdout',
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": LOG_FILE,
            "mode": "a",
            "encoding": "utf-8",
            "maxBytes": 500000,
            "backupCount": 2
        }
    },
    "loggers": {
        "console": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        }
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger('console')

if FILESYSTEMS not in ['diskfs', 'memfs']:
    raise ValueError(f"Invalid FILESYSTEMS value: {filesystems}. Must be 'diskfs' or 'memfs'.")

logger.info(f"Using filesystem: {FILESYSTEMS}")

def handle_exception(exc_type, exc_value, exc_traceback):
    """Captura si logare exceptii neprevazute."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception
# logger end.

process_config = ProcessConfig(
    id="dummy",
    reference=PROCESS_REFERENCE,
    options=["-loglevel", "level+info", "-err_detect", "ignore_err", "-y"],
    input=[
        ProcessConfigIO(
            address="dummy",
            id="input_0",
            options=[
                "-fflags", "+genpts",
                "-thread_queue_size", "512",
                "-probesize", "5000000",
                "-analyzeduration", "3000000",
                "-rtmp_enhanced_codecs", "hvc1,av01,vp09"
            ]
        )
    ],
    output=[
        ProcessConfigIO(
            address=f"{{{FILESYSTEMS}}}/{{processid}}_{{outputid}}.m3u8",
            id="0",
            options=[
                "-map", "0:1",
                "-codec:v", "copy",
                "-map", "0:0",
                "-codec:a", "copy",
                "-f", "hls",
                "-bsf:v", "h264_mp4toannexb",
                "-hls_init_time", "0",
                "-start_number", "0",
                "-hls_time", "6",
                "-hls_list_size", "6",
                "-hls_flags", "append_list+delete_segments+program_date_time+temp_file",
                "-hls_delete_threshold","2",
                "-hls_start_number_source", "generic",
                "-hls_allow_cache", "0",
                "-hls_enc", "0",
                "-hls_segment_filename", f"{{{FILESYSTEMS}}}/{{processid}}_{{outputid}}_%d.ts",
                "-master_pl_name", "{processid}.m3u8",
                "-master_pl_publish_rate", "2",
                "-method", "PUT",
                "-http_persistent", "1",
                "-ignore_io_errors", "0"
            ],
            cleanup=[
                ProcessConfigIOCleanup(
                    pattern=f"{FILESYSTEMS}:/{{processid}}**",
                    purge_on_delete=True
                ),
                ProcessConfigIOCleanup(
                    pattern=f"{FILESYSTEMS}:/{{processid}}_{{outputid}}.m3u8",
                    max_file_age_seconds=60,
                    purge_on_delete=True
                ),
                ProcessConfigIOCleanup(
                    pattern=f"{FILESYSTEMS}:/{{processid}}_{{outputid}}_**.ts",
                    max_files=24,
                    max_file_age_seconds=60,
                    purge_on_delete=True
                ),
                ProcessConfigIOCleanup(
                    pattern=f"{FILESYSTEMS}::/{{processid}}.m3u8",
                    max_file_age_seconds=60,
                    purge_on_delete=True
                )
            ]
        )
    ],
    limits=ProcessConfigLimit(
        cpu_usage=0,
        memory_mbytes=0,
        waitfor_seconds=0
    ),
    autostart=True,
    reconnect=True,
    reconnect_delay_seconds=4,
    stale_timeout_seconds=20,
)

def is_valid_stream_key(value: str):
    """ """
    pattern = os.getenv("STREAM_KEY_PATTERN", r"^[A-Z]{4}-[a-z0-9]{6}$")
    return bool(re.match(pattern, value))


def config_is_uptodate(rtmp_process_config: dict, core_process_config: dict):
    """ """
    compare_config = merge(core_process_config, rtmp_process_config)
    if compare_config == core_process_config:
        return False
    return True


def create_process_config():
    """creates an process config for rtmp list."""
    process_list = []
    for core_rtmp in core_rtmp_list:
        rtmp_name = core_rtmp.name.split('/')[-1]

        if is_valid_stream_key(rtmp_name):
            config = deepcopy(process_config)
            config.id = rtmp_name
            config.input[0].address = f"{{rtmp,name={rtmp_name}}}"
            process_list.append(config)

    return process_list


def create_processes(rtmp_process_list: list):
    """creates or updates each stream file process
    on the assigned core url.

    Args:
        rtmp_process_list (list): list of stream file configs.
    """
    for rtmp_process in rtmp_process_list:
        is_unknown = True
        for core_process in core_process_list:
            if (rtmp_process.id == core_process.id and core_process.reference == PROCESS_REFERENCE):
                is_unknown = False
                if config_is_uptodate(
                    rtmp_process_config=rtmp_process.dict(),
                    core_process_config=core_process.config.dict()
                ):
                    measure_and_log(f'Update process id "{rtmp_process.id}"', client.v3_process_put, id=core_process.id, config=rtmp_process, log_level=logging.INFO)
                    send_webhook(rtmp_process.id, "publish")
        if is_unknown:
            measure_and_log(f'Create process id "{rtmp_process.id}"', client.v3_process_post, config=rtmp_process, log_level=logging.INFO)
            send_webhook(rtmp_process.id, "publish")


def clear_core_processes(rtmp_process_list: list):
    """removes all processes with PROCESS_REFERENCE
    and if not exists in rtmp_process_list.

    Args:
        rtmp_process_list (list): list of stream file configs.
    """
    for core_process in core_process_list:
        if core_process.reference == PROCESS_REFERENCE:
            is_unknown = True
            for rtmp_process in rtmp_process_list:
                if (rtmp_process.id == core_process.id and core_process.reference == PROCESS_REFERENCE):
                    is_unknown = False
            if is_unknown:
                measure_and_log(f'Delete process id "{core_process.id}"', client.v3_process_delete, id=core_process.id, log_level=logging.INFO)
                send_webhook(core_process.id, "unpublish")


def measure_and_log(action_name, func, *args, log_level=logging.DEBUG, **kwargs):
    """Masoara timpul unei funtii si logheaza rezultatul."""
    start_time = time.time()
    result = func(*args, **kwargs)

    end_time = time.time()
    execution_time = end_time - start_time

    # Logare cu nivelul specificat
    time_exec = f"{execution_time:.2f} sec"
    if (log_level == logging.INFO):
        time_exec = f" {execution_time:.2f} sec"

    if isinstance(result, Error):
        logger.error(f"{time_exec} - {action_name} - {result.message}")
    else:
        logger.log(log_level, f"{time_exec} - {action_name}")

    return result


def send_webhook(rtmp_id, type):
    if not WEBHOOK_URL:
        return

    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "stream_id": rtmp_id,
        "protocol": "RTMP",
        "host": HOST,
        "type": type,
        "time": int(time.time() * 1000)
    }

    try:
        start_time = time.time()

        response = requests.post(
            WEBHOOK_URL, headers=headers, data=json.dumps(data))

        end_time = time.time()
        execution_time = end_time - start_time

        if response.status_code == 200:
            logger.info(
                f" {execution_time:.2f} sec - Send Webhook url: {WEBHOOK_URL}, rtmp_id: {rtmp_id}")
        else:
            logger.error(
                f"{execution_time:.2f} sec - Error: Send Webhook url: {WEBHOOK_URL}, rtmp_id: {rtmp_id}, status: {response.status_code}")

    except Exception as e:
        logger.error(f"Error: {e}")


# core connection and login
try:
    client = Client(
        base_url=CORE_ADDRESS,
        username=CORE_USERNAME,
        password=CORE_PASSWORD
    )
    client.login()
except Exception as e:
    error_message = (
        f"base_url: {CORE_ADDRESS} "
        f"username: {CORE_USERNAME} "
        f"password: {CORE_PASSWORD} "
        f"Error: {e}"
    )
    logger.error(error_message)
    raise RuntimeError(error_message)

# start the loop
last_core_rtmp_list = None

try:
    get_config = measure_and_log("Get config", client.v3_config_get)
    HOST = get_config.config.host.name[0]

    logger.info(f"Core host: {HOST}")

    while True:
        try:
            core_rtmp_list = measure_and_log("Fetching rtmp list", client.v3_rtmp_get)

            if sorted(str(core_rtmp_list)) != sorted(str(last_core_rtmp_list)):
                last_core_rtmp_list = core_rtmp_list

                core_process_list = measure_and_log("Fetching process list", client.v3_process_get_list, reference=PROCESS_REFERENCE)
                # print(core_process_list)

                # create a temp. list of stream file configs
                input_process_list = create_process_config()
                # print(input_process_list)


                # create or update stream file processes
                create_processes(rtmp_process_list=input_process_list)

                # remove dropped stream file on core
                clear_core_processes(rtmp_process_list=input_process_list)

        except Exception as e:
            logger.error(f"error: {e}")

        time.sleep(SYNC_INTERVAL_SECONDS)
except KeyboardInterrupt:
    logger.debug("Run return except: KeyboardInterrupt")
except SystemExit:
    logger.debug("Run return except: SystemExit")
