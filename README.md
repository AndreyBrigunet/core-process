# datarhei Core - Creaza flux hls din rtmp automat
This Python application (Python 3.10, [Core PyClient](https://github.com/datarhei/core-client-python)) demonstrates how to interact with the [datarhei Core](https://github.com/datarhei/core).


1. Creaza retea comuna 
    ```sh
    docker network create core
    ```

2. Adaugat la core in docker-compose.yml
    ```sh
        networks:
        - core

    networks:
    core:
        external: true
    ```

3. Seteaza Enviroments

- `CORE_ADDRESS` (lasa gol)
- `CORE_USERNMAE` (default: unset)
- `CORE_PASSWORD` (default: unset)
- `PROCESS_REFERENCE` (default: rtmp:hls)
- `SYNC_INTERVAL_SECONDS` (default: 10)


4. Build si start
    ```sh
    git clone https://github.com/AndreyBrigunet/core-process.git
    cd core-process
    docker compose build
    docker compose up -d
    ```
