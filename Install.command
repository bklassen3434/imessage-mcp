#!/bin/bash
# Double-clickable wrapper so nobody has to open Terminal themselves.
cd "$(dirname "${BASH_SOURCE[0]}")"
./install.sh
echo ""
echo "Press Return to close this window."
read -r _
