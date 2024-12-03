#!/bin/bash

# Fail-fast pe erori si variabile nedefinite
set -euo pipefail

# Obtine IP-ul containerului
CONTAINER_NAME="core"
CONTAINER_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTAINER_NAME" 2>/dev/null)

# Verifica daca IP-ul a fost obtinut
if [[ -z "$CONTAINER_IP" ]]; then
    echo "Eroare: Nu s-a putut obtine IP-ul pentru containerul '$CONTAINER_NAME'."
    exit 1
fi

# Actualizeaza doar CORE_ADDRESS în fisierul .env
sed -i "s|^CORE_ADDRESS=.*|CORE_ADDRESS=http://$CONTAINER_IP:8080|" /app/.env

echo "CORE_ADDRESS actualizat in .env: http://$CONTAINER_IP:8080"
