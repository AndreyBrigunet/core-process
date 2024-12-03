import os
import time
import re
from copy import deepcopy
from enum import Enum
from jsonmerge import merge

from core_client import Client
from core_client.base.models.v3 import (
    ProcessConfig,
    ProcessConfigLimit,
    ProcessConfigIO,
    ProcessConfigIOCleanup
)

# Local
# from dotenv import load_dotenv
# load_dotenv()

CORE_ADDRESS = os.getenv('CORE_ADDRESS', '')
CORE_USERNAME = os.getenv('CORE_USERNAME', '')
CORE_PASSWORD = os.getenv('CORE_PASSWORD', '')

PROCESS_REFERENCE = os.getenv('PROCESS_REFERENCE', 'rtmp:hls')
SYNC_INTERVAL_SECONDS = int(os.getenv('SYNC_INTERVAL_SECONDS', 10))

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
            address="{memfs}/{processid}_{outputid}.m3u8",
            id="output_0",
            options=[
                "-dn", "-sn",
                "-map", "0:1",
                "-codec:v", "copy",
                "-map", "0:0",
                "-codec:a", "copy",
                "-f","hls",
                "-start_number","0",
                "-hls_time","6",
                "-hls_list_size","6",
                "-hls_flags","append_list+delete_segments+program_date_time+temp_file",
                "-hls_delete_threshold","4",
                "-hls_segment_filename","{memfs}/{processid}_{outputid}_%04d.ts",
                "-master_pl_name","{processid}.m3u8",
                "-master_pl_publish_rate","2",
                "-method","PUT"
            ],
            cleanup=[
                ProcessConfigIOCleanup(
                    pattern="memfs:/{processid}**",
                    purge_on_delete=True
                ),
                ProcessConfigIOCleanup(
                    pattern="memfs:/{processid}_{outputid}.m3u8",
                    max_file_age_seconds=60,
                    purge_on_delete=True
                ),
                ProcessConfigIOCleanup(
                    pattern="memfs:/{processid}_{outputid}_**.ts",
                    max_files=24,
                    max_file_age_seconds=60,
                    purge_on_delete=True
                ),
                ProcessConfigIOCleanup(
                    pattern="memfs:/{processid}.m3u8",
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
    pattern = r"^[A-Z]{4}-[a-z0-9]{6}$"
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
                    print(f'update process id "{rtmp_process.id}"')
                    client.v3_process_put(id=core_process.id, config=rtmp_process)
        if is_unknown:
            print(f'create process id "{rtmp_process.id}"')
            client.v3_process_post(config=rtmp_process)


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
                print(f'delete process id "{core_process.id}"')
                client.v3_process_delete(id=core_process.id)


# core connection and login
client = Client(
    base_url=CORE_ADDRESS,
    username=CORE_USERNAME,
    password=CORE_PASSWORD
)
client.login()

# start the loop
try:
    while True:
        try:
            input_process_list = []
            start_time = time.time() 
            core_rtmp_list = client.v3_rtmp_get()
            end_time = time.time() 
            execution_time = end_time - start_time
            print(f"timpul executie: v3_rtmp_get: {execution_time:.2f} secunde")
            # print(core_rtmp_list)
            
            # if core_rtmp_list:
            start_time = time.time()
            core_process_list = client.v3_process_get_list(reference=PROCESS_REFERENCE)
            end_time = time.time() 
            execution_time = end_time - start_time
            print(f"timpul executie: v3_process_get_list: {execution_time:.2f} secunde")

            # print(core_process_list)
        
            # create a temp. list of stream file configs
            input_process_list = create_process_config()
            # print(input_process_list)

            
            # create or update stream file processes
            create_processes(rtmp_process_list=input_process_list)

            # remove dropped stream file on core
            clear_core_processes(rtmp_process_list=input_process_list)
        
        except Exception as e:
            print(f"error: {e}")

        time.sleep(SYNC_INTERVAL_SECONDS)
except KeyboardInterrupt:
    print("Run return except: KeyboardInterrupt")
except SystemExit:
    print("Run return except: SystemExit")