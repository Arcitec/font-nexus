#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2023 Arcitec
# SPDX-License-Identifier: MPL-2.0
#
# Font-Nexus
# https://github.com/Arcitec/font-nexus


SCRIPT_DIR="$(dirname -- "${BASH_SOURCE[0]}")"
SOURCE_DIR="${SCRIPT_DIR}/output/"
TARGET_DIR="/usr/local/share/fonts/font-nexus/"


echo -e "Font-Nexus [https://github.com/Arcitec/font-nexus]\n"

yell() { echo "${0}: ${*}"; }

# Check arguments.
DO_BUILD=0
DO_INSTALL=0
display_help() {
    echo -e "Usage: \"${0}\" [ARGS]\n"
    echo "Available arguments:"
    echo "  -b  Perform a clean build before the installation."
    echo "  -i  Install the fonts."
    echo "  -h  Display help."
    exit ${1:-0}
}
while getopts "bih" arg; do
    case $arg in
        b)
            DO_BUILD=1
            ;;
        i)
            DO_INSTALL=1
            ;;
        h | *)
            if [[ "${arg}" != "h" ]]; then display_help 1; else display_help; fi
            ;;
    esac
done

DID_NOTHING=1

# Build the fonts.
if [[ $DO_BUILD -eq 1 ]]; then
    python "${SCRIPT_DIR}/build.py" || exit 1
    DID_NOTHING=0
fi

# Install the fonts.
if [[ $DO_INSTALL -eq 1 ]]; then
    if [[ $DO_BUILD -eq 1 ]]; then echo ""; fi # Oooh, pretty spaces!

    if [[ ! -d "${SOURCE_DIR}" ]]; then
        yell "Can't install. There is no build output. Please run \"-b\" first."
        display_help 1
    fi

    # NOTE: We sync in "delete" mode, to remove any outdated orphans from target,
    # and we append an extra trailing "/" just in case someone edits this script
    # and forgets to include the trailing slashes that rsync requires.
    echo "Installing..."
    sudo rsync -av --no-p --no-o --no-g --chmod=ugo=rwX --delete --mkpath "${SOURCE_DIR}/" "${TARGET_DIR}/" || exit 1

    # Update SELinux security contexts (only if computer has it).
    if command -v "restorecon"; then
        sudo restorecon -RFv "${TARGET_DIR}" || exit 1
    fi

    # Update the system-wide font cache.
    # NOTE: Most fontconfig-based applications also do this automatically at startup.
    sudo fc-cache -v || exit 1

    echo "Installation complete."
    DID_NOTHING=0
fi

if [[ $DID_NOTHING -eq 1 ]]; then
    yell "You must provide at least one argument."
    display_help 1
fi
