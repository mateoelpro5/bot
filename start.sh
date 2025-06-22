#!/bin/bash

echo "Iniciando bucle de ejecución del bot..."

while true
do
  echo "🔄 Lanzando bot..."
  /opt/venv/bin/python main.py
  echo "❌ El bot se detuvo. Reiniciando en 5 segundos..."
  sleep 5
done
