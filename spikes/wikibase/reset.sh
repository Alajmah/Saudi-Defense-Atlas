#!/usr/bin/env sh
set -eu

docker compose down -v --remove-orphans
rm -f state.generated.json verification.generated.json

printf '%s\n' 'Wikibase M0 spike state reset.'
