FROM python:3.10-alpine

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

ENTRYPOINT ["sh", "-c", "\
    if [ -z \"$CORE_ADDRESS\" ]; then \
    CONTAINER_IP=$(getent hosts core | awk '{ print $1 }'); \
    export CORE_ADDRESS=http://$CONTAINER_IP:8080; \
    echo \"CORE_ADDRESS set to $CORE_ADDRESS\"; \
    fi && \
    python src/main.py"]