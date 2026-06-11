#!/usr/bin/env bash
# leak-audit.sh — assert the OSS tree carries ZERO estate artifacts.
#
# Estate artifact classes (story acceptance: hostnames / bearers / card-ids):
#   - internal hostnames + Tailscale IPs
#   - board card ids (kt_<epoch>_<hex>)
#   - estate filesystem paths (/home/henry, /home/ubuntu)
#   - estate service endpoints (kanban :8649, gates-bot :8688, mcphub, cliproxy)
#   - credential-shaped strings (actual values; the word "bearer" inside the
#     advisory regex that DETECTS credentials is expected and excluded)
#   - personal names tied to the estate
#
# Exit 0 = clean, exit 1 = leaks listed on stdout.
set -uo pipefail
cd "$(dirname "$0")/.."

PATTERNS=(
  'kt_[0-9]{9,}'                       # board card ids
  '100\.(6[4-9]|[7-9][0-9]|1[0-2][0-9])\.[0-9]+\.[0-9]+'  # Tailscale CGNAT IPs
  '/home/(henry|ubuntu|mally)'         # estate paths
  ':8649|:8688|:8317|:8920|:8917|:8918' # estate service ports
  'mcphub|cliproxy|gates-bot|litellm'  # estate services
  'tailscale|aeros\b|mac-mini|macbook' # estate hosts
  'berlai|jiddlers|hermes'             # estate/tenant names
  '\bmally\b|\bhenry\b|berliand'       # personal names
  'ANTHROPIC_API_KEY|sk-[A-Za-z0-9]{20}' # credential shapes
)

fail=0
for pat in "${PATTERNS[@]}"; do
  hits=$(grep -rniE "$pat" \
           --include='*.py' --include='*.md' --include='*.toml' \
           --include='*.sh' --include='*.txt' \
           --exclude-dir=.git --exclude-dir=__pycache__ \
           . 2>/dev/null | grep -v 'tools/leak-audit.sh')
  if [ -n "$hits" ]; then
    echo "LEAK [$pat]:"
    echo "$hits"
    fail=1
  fi
done

if [ "$fail" -eq 0 ]; then
  echo "LEAK-AUDIT-CLEAN"
fi
exit "$fail"
