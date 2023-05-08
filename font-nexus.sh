#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2023 Arcitec
# SPDX-License-Identifier: MPL-2.0
#
# Font-Nexus
# https://github.com/Arcitec/font-nexus


SCRIPT_DIR="$(dirname -- "${BASH_SOURCE[0]}")"
SOURCE_DIR="${SCRIPT_DIR}/output/"
SYSTEM_TARGET_DIR="/usr/local/share/fonts/font-nexus/"
LOCAL_TARGET_DIR="${HOME}/.local/share/fonts/font-nexus/"
TARGET_DIR="${SYSTEM_TARGET_DIR}"


echo -e "Font-Nexus [https://github.com/Arcitec/font-nexus]\n"

yell() { echo "${0}: ${*}"; }

# Check arguments.
DO_BUILD=0
DO_INSTALL=0
display_help() {
    echo -e "Usage: \"${0}\" [ARGS]\n"
    echo "Available arguments:"
    echo "  -b         Perform a clean build before the installation."
    echo "  -i         Install the fonts (system-wide by default, unless modified by another flag)."
    echo "  -l         Install to local home-path (~/.local/share/fonts) instead."
    echo "  -p <path>  Install to custom path instead (a \"font-nexus\" sub-dir is automatically created)."
    echo "  -h         Display help."
    exit ${1:-0}
}
while getopts "bilp:h" arg; do
    case $arg in
        b)
            DO_BUILD=1
            ;;
        i)
            DO_INSTALL=1
            ;;
        l)
            DO_INSTALL=1 # Allows use of -l as shorthand for -i -l.
            TARGET_DIR="${LOCAL_TARGET_DIR}"
            ;;
        p)
            DO_INSTALL=1 # Allows use of -p as shorthand for -i -p.
            TARGET_DIR="${OPTARG}/font-nexus/"
            if [[ "${OPTARG}" = "" ]]; then
                yell "You must provide a non-empty custom path."
                display_help 1
            fi
            ;;
        h | *)
            if [[ "${arg}" != "h" ]]; then display_help 1; else display_help; fi
            ;;
    esac
done

DID_NOTHING=1

# Verify that target path begins with a slash (relative paths aren't allowed).
# NOTE: Typical `~/` paths will be expanded by shell to absolute paths before
# being sent to us, so those will still work as arguments.
if [[ "${TARGET_DIR}" != /* ]]; then
    yell "Your custom path must be absolute (must begin with \"/\")."
    display_help 1
fi

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

    # Figure out if this is a home-folder (local) target or a root target.
    # NOTE: To simplify things, we'll assume that every home is ours (no sudo).
    NEEDS_SUDO=1
    if [[ "${TARGET_DIR}" == /home/* ]]; then
        NEEDS_SUDO=0
    fi

    # NOTE: We create the target if it doesn't exist.
    # NOTE: We sync in "delete" mode, to remove any outdated orphans from target,
    # and we append an extra trailing "/" just in case someone edits this script
    # and forgets to include the trailing slashes that rsync requires.
    echo "Installing..."
    if [[ $NEEDS_SUDO -eq 1 ]]; then
        sudo mkdir -p "${TARGET_DIR}/"
        sudo rsync -av --no-p --no-o --no-g --chmod=ugo=rwX --delete --mkpath "${SOURCE_DIR}/" "${TARGET_DIR}/" || exit 1
    else
        mkdir -p "${TARGET_DIR}/"
        rsync -av --no-p --no-o --no-g --chmod=ugo=rwX --delete --mkpath "${SOURCE_DIR}/" "${TARGET_DIR}/" || exit 1
    fi

    # Update SELinux security contexts (only if computer has it).
    # NOTE: This works for local home files without sudo too.
    if command -v "restorecon"; then
        if [[ $NEEDS_SUDO -eq 1 ]]; then
            sudo restorecon -RFv "${TARGET_DIR}" || exit 1
        else
            restorecon -RFv "${TARGET_DIR}" || exit 1
        fi
    fi

    # Update the font cache (either system-wide or just for the local user).
    # NOTE: Most fontconfig-based applications also do this automatically at startup.
    if [[ $NEEDS_SUDO -eq 1 ]]; then
        sudo fc-cache -v || exit 1
        # We also need to update the local "~/.cache" for the invoking user,
        # but let's do this final step silently when it's a global install.
        # NOTE: If the user runs this whole installer as "sudo", we won't be
        # updating their real, local cache, but their own apps will deal with
        # that later anyway, so it's no problem whatsoever.
        fc-cache >/dev/null 2>&1
    else
        fc-cache -v || exit 1
    fi

    echo "Installation complete."
    DID_NOTHING=0
fi

if [[ $DID_NOTHING -eq 1 ]]; then
    yell "You must provide at least one argument."
    display_help 1
fi
