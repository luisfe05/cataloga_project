#!/bin/bash
# Build Cataloga.app with PyInstaller.
#
# Run it from the cataloga folder, with the virtual environment active:
#     source venv/bin/activate
#     ./build.sh
# The app is created at dist/Cataloga.app.

# Stop at the first error instead of building a broken app.
set -e

# --windowed        make a Mac .app with no Terminal window
# --icon            the app icon shown in Finder and the Dock
# --add-data        include the frontend folder (HTML, CSS, JS)
# --hidden-import   keyring picks its macOS backend at runtime, so
#                   PyInstaller can't see that it is needed
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
