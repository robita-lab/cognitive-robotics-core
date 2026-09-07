#!/usr/bin/env bash
# Alias histórico — usa ./UDITO o ./scripts/Principal-UDITO.sh
exec "$(cd "$(dirname "$0")" && pwd)/Principal-UDITO.sh" "$@"
