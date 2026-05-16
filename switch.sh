#!/bin/bash
cd "$(dirname "$0")/extension" || exit 1
case "${1:-}" in
  firefox) cp manifests/firefox.json manifest.json; echo "✅ Firefox mode active"; ;;
  chrome)  cp manifests/chrome.json manifest.json; echo "✅ Chrome mode active"; ;;
  *)
    echo "Usage: bash switch.sh [chrome|firefox]"
    echo "  chrome  - sidePanel + service_worker"
    echo "  firefox - sidebar_action + scripts"
    exit 1
    ;;
esac
