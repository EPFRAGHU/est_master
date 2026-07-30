#!/bin/bash
# ============================================================
#  Build Establishment Master Search as a standalone executable
#  Run:  bash build_mac_linux.sh
#  Requires Python installed once - after that, no Python
#  needed to RUN the app, only to BUILD it this one time.
# ============================================================

set -e
echo "Installing required packages (one-time)..."
pip3 install --user pyinstaller pandas openpyxl

echo ""
echo "Building EstablishmentMasterSearch ..."
pyinstaller --onefile --windowed --name EstablishmentMasterSearch establishment_search.py

echo ""
echo "============================================================"
echo "  DONE."
echo "  Your app is at:  dist/EstablishmentMasterSearch"
echo ""
echo "  Copy that file and establishment_master.csv into the"
echo "  SAME folder together, then just double-click (or run"
echo "  ./EstablishmentMasterSearch) - no Python needed after this."
echo "============================================================"
