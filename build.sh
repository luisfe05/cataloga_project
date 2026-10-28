#!/bin/bash
# Build Cataloga.app with PyInstaller. Run ./build.sh from cataloga/ with the venv active.

set -e

# --windowed        make a Mac .app with no Terminal window
# --icon            the app icon shown in Finder and the Dock
# --add-data        include the frontend folder (HTML, CSS, JS)
# --hidden-import   keyring picks its macOS backend at runtime, hidden from PyInstaller
# --specpath build  keep the generated .spec file out of the repo
# --noconfirm       replace the previous build without asking
# --clean           start from an empty build cache
pyinstaller \
    --name Cataloga \
    --windowed \
    --icon "$(pwd)/assets/Cataloga.icns" \
    --add-data "$(pwd)/frontend:frontend" \
    --hidden-import keyring.backends.macOS \
    --specpath build \
    --noconfirm \
    --clean \
    main.py

echo "Done: dist/Cataloga.app"
