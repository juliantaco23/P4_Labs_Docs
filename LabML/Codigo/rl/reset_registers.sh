#!/bin/bash
# reset_registers.sh — Reinicia los registros de conteo en s1
# Llama a register_reset para limpiar synReg y synAckRstReg.
# Útil para reiniciar el estado del switch entre experimentos.
#
# Uso: ./reset_registers.sh [thrift_port]
#   Ej: ./reset_registers.sh 9090

PORT=${1:-9090}
echo "[RESET] Resetting registers on port $PORT..."
simple_switch_CLI --thrift-port "$PORT" <<< 'register_reset MyIngress.synReg'       > /dev/null
simple_switch_CLI --thrift-port "$PORT" <<< 'register_reset MyIngress.synAckRstReg' > /dev/null
echo "[RESET] Done."
