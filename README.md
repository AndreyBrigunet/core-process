# datarhei Core - Streamfile importer
This Python application (Python 3.10, [Core PyClient](https://github.com/datarhei/core-client-python)) demonstrates how to interact with the [datarhei Core](https://github.com/datarhei/core). The application enables local files to generate FFmpeg processes, which consider the file name and file content (stream URL) and make the corresponding stream URL available as HLS, RTMP, and/or SRT streams.

The application is designed to be responsive to new files, file changes, and file deletions. However, it currently only supports H.264 and AAC live-streams.

## Installation steps (Linux/macOS example)

1. Start the Core and enable the built-in RTMP and SRT servers    
    ```sh
    docker run -d --name core \
        --security-opt seccomp=unconfined \
        -p 8080:8080 -p 1935:1935 -p 6000:6000/udp \
        -e CORE_RTMP_ENABLE=true -e CORE_SRT_ENABLE=true \
        datarhei/core:latest
    ```

2. Get the internal `CORE_ADDRESS`   
    ```sh
    docker inspect -f '{{ .NetworkSettings.IPAddress }}' core
    ```

    Example: 172.17.0.2

    *This allows the application to communicate with the Core. As an alternative, you can also use the IP address of the host system.*

De adaugat la core docker-compose.yml
    ```sh
        networks:
        - core

    networks:
    core:
        external: true
    ```

    ```sh
    docker network create core
    ```

3. Build and start the Streamfile-Importer
    ```sh
    git clone https://github.com/AndreyBrigunet/core-process.git
    cd core-process
    docker compose build
    docker compose up -d
    ```


## Enviroments

- `CORE_ADDRESS` (default: unset)
- `CORE_USERNMAE` (default: unset)
- `CORE_PASSWORD` (default: unset)
- `PROCESS_REFERENCE` (default: rtmp:hls)
- `SYNC_INTERVAL_SECONDS` (default: 10)

