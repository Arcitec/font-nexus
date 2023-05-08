# SPDX-FileCopyrightText: 2023 Arcitec
# SPDX-License-Identifier: MPL-2.0
#
# Font-Nexus
# https://github.com/Arcitec/font-nexus

from pathlib import Path
import datetime
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request


BASE_PATH = Path(sys.argv[0]).parent
OUTPUT_PATH = BASE_PATH / "output"
SOURCE_PATH = BASE_PATH / "source"
TEMP_PATH = BASE_PATH / "temp"


def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def bytes_to_mib(bytes: int) -> str:
    mib = bytes / (1024 * 1024)
    return f"{mib:.02f} MiB"


def rmtree(dir_name: Path) -> None:
    if not dir_name.exists():
        return

    if not shutil.rmtree.avoids_symlink_attacks:
        print(
            f'Your system doesn\'t have a symlink-safe rmtree implementation. Please manually delete "{dir_name}" and try again.'
        )
        exit(1)

    shutil.rmtree(dir_name)


def create_font_output(dir_name: str) -> Path:
    target_path = OUTPUT_PATH / dir_name

    if target_path.exists():
        # Ensure that output target is clean.
        rmtree(target_path)

    target_path.mkdir(
        mode=0o755, parents=True, exist_ok=False
    )  # Throws if still exists.

    return target_path


def copy_font(font_file: Path, target_base_path: Path) -> Path:
    # Figure out the generic family name to nicely sort the font.
    font_family = get_font_family(font_file)
    family_path = target_base_path / font_family
    if not family_path.exists():
        family_path.mkdir(mode=0o755, parents=True, exist_ok=True)

    # Perform a copy of the contents (not metadata), and throws if error.
    dest_font_file = family_path / font_file.name
    shutil.copyfile(font_file, dest_font_file, follow_symlinks=True)
    print(f'* "{dest_font_file}"')

    return dest_font_file


def run_ext(args: list[str], cwd: str | Path = None, encoding: str = "utf-8") -> str:
    # We don't care about handling errors, so "check" simply throws if non-zero.
    res = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        # Capture STDOUT, but we ignore (pass through) STDERR to the user.
        stdout=subprocess.PIPE,
        # stderr=subprocess.PIPE,
        encoding=encoding,
    )

    return res.stdout


def download_if_newer(url: str, output_path: Path) -> None:
    if not output_path.exists():
        output_path.mkdir(mode=0o755, parents=True, exist_ok=True)

    # Run wget, since it robustly handles downloads and timestamping. The user
    # will still see progress, since wget uses STDERR for all status messages.
    run_ext(
        [
            "wget",
            # Disable the most verbose output (such as headers/redirect info).
            "--quiet",
            # Still display progress for the actual downloading.
            "--show-progress",
            # Only download files if new or updated since last time.
            "--timestamping",
            # We must change the output directory prefix. We cannot use wget's
            # "output filename" option, because it deletes the target and thereby
            # always creates a new file, thus never working properly.
            "--directory-prefix",
            str(output_path.absolute()),
            # The output filename will be based on whatever filename the server
            # returns to us.
            url,
        ]
    )


def get_font_family(font_file: Path) -> str:
    # Get all English names for the font, or fail if no English found.
    # NOTE: All fonts seem to have English names, as a standardized rule.
    raw_result = run_ext(
        [
            "fc-scan",
            "--format",
            # This crazy pattern comes from "man FcPatternFormat", and it simply
            # expands every font family name and the language of that name,
            # on individual lines.
            "%{[]family,familylang{%{family} (%{familylang})\n}}",
            str(font_file.absolute()),
        ]
    )
    english_names = re.findall(r"(?m)^(.+?) \(en\)$", raw_result)
    if not english_names:
        raise LookupError(f'No english names in font "{font_file.name}".')

    # Return the first English family name, since fonts always seem to list the
    # primary family name first, and more specific names later.
    return english_names[0]


def get_web_text(url: str, encoding: str = "utf-8") -> str:
    # Throws if there are any issues with the fetching or decoding.
    with urllib.request.urlopen(url) as f:
        return f.read().decode(encoding)


def process_microsoft(windows_version: int = 11) -> int:
    # Verify source folder existence.
    source_fonts = SOURCE_PATH / "windows/Fonts"
    if not source_fonts.is_dir():
        print(
            f'Missing "{source_fonts}". Copy it from a fully updated "C:\\Windows\\Fonts" installation, and be sure to use the latest edition of Windows {windows_version}.'
        )
        exit(1)

    # Fetch font groups from Arch's AUR package (for easy filtering of unwanted fonts).
    # NOTE: The given "windows_version" must point at a valid PKGSPEC. Historically,
    # all AUR packages for Windows 10 and 11 fonts have used this naming pattern.
    font_groups = {}
    upstream_pkg_base = "https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD"
    upstream_pkg_url = f"{upstream_pkg_base}?h=ttf-ms-win{windows_version}-auto"
    raw_pkgspec = get_web_text(upstream_pkg_url)
    for m_grp in re.finditer(r"(?s)_ttf_ms_([^=]+)=\((.+?)\n\)", raw_pkgspec):
        group_name = m_grp.group(1)

        font_groups[group_name] = []
        for m_font in re.finditer(r"(\S+)", re.sub(r"(?m)#.*$", "", m_grp.group(2))):
            font_groups[group_name].append(m_font.group(1))

    # Figure out which filters we want to use. By default, we skip all Asian fonts,
    # since their files are utterly humongous.
    # NOTE: The user can specify the environment variable to change the groups.
    enabled_ms_groups = os.getenv("WINDOWS_FONT_GROUPS", "win11,win11_other")
    enabled_ms_groups = enabled_ms_groups.split(",")

    # Analyze groups and their total filesizes, and validate file existence.
    group_stats = {"enabled": [], "disabled": [], "size_enabled": 0, "size_disabled": 0}
    for group_name in sorted(font_groups.keys()):
        group_size = 0
        for font_file in font_groups[group_name]:
            font_file = source_fonts / font_file
            if not font_file.is_file():
                print(
                    f'Missing "{font_file}" for group "{group_name}". Please fix your source Fonts directory, and ensure that it comes from a fully updated Windows {windows_version} installation.'
                )
                exit(1)
            group_size += font_file.stat().st_size

        group_stats[
            "enabled" if group_name in enabled_ms_groups else "disabled"
        ].append({"group_name": group_name, "group_size": group_size})

        group_stats[
            "size_enabled" if group_name in enabled_ms_groups else "size_disabled"
        ] += group_size

    # Display statistics for the enabled and disabled groups.
    for x in ["enabled", "disabled"]:
        print(
            f"{x.capitalize()} Microsoft font groups ({bytes_to_mib(group_stats[f'size_{x}'])}):"
        )
        for group_info in group_stats[x]:
            print(
                f"{'+' if x == 'enabled' else '-'} {group_info['group_name']}: {bytes_to_mib(group_info['group_size'])}"
            )
        print("")

    # Create the actual font output directory.
    target_path = create_font_output("windows-fonts")

    # Scan all enabled font groups and copy them into the correct output directories, sorted by family name.
    print("Copying selected Microsoft fonts...")
    final_size = 0
    for group_name in font_groups:
        if group_name in enabled_ms_groups:
            for font_file in font_groups[group_name]:
                font_file = source_fonts / font_file
                target_file = copy_font(font_file, target_path)
                final_size += target_file.stat().st_size

    print(f"\nOutput font size (Microsoft): {bytes_to_mib(final_size)}.\n")

    return final_size


def process_apple() -> int:
    # Fetch the URLs for all DMG packages.
    raw_html = get_web_text("https://developer.apple.com/fonts/")
    dmg_urls = re.findall(r'(?m)http[^"]+?\.dmg', raw_html)
    if not dmg_urls:
        print("Couldn't find any DMG files on Apple's fonts website.")
        exit(1)

    # Download any missing or modified DMG files.
    # NOTE: This is incredibly fast if "temp" already exists, since it only
    # downloads the files if they've changed since last time.
    print("Downloading new or updated Apple font DMG files...")
    process_dmgs = []
    dmg_source_path = SOURCE_PATH / "apple-dmgs"
    for dmg_url in dmg_urls:
        download_if_newer(dmg_url, dmg_source_path)
        # NOTE: Thanks to our regex we know that every URL ends in ".dmg".
        process_dmgs.append(dmg_source_path / os.path.basename(dmg_url))
    print("")

    # Verify that all expected files exist locally, and larger than 0 bytes.
    for dmg_file in process_dmgs:
        if not dmg_file.is_file() or dmg_file.stat().st_size < 1:
            print(f'Missing "{dmg_file}". Please try again.')
            exit(1)

    # Ensure that the temporary extraction path exists and is empty.
    dmg_extract_path = TEMP_PATH / "apple-extract"
    rmtree(dmg_extract_path)
    dmg_extract_path.mkdir(mode=0o755, parents=True, exist_ok=True)

    # Extract the layered Apple DMG files.
    # NOTE: If 7zip errors anytime, we'll automatically throw an error and abort.
    print("Extracting Apple font packages...")

    # First extract the font's ".pkg" file from the ".dmg" container.
    for dmg_file in process_dmgs:
        run_ext(
            [
                "7z",
                "e",  # Extract.
                # Only extract the Fonts.pkg file (via wildcard), nothing else.
                r"-ir!*Fonts.pkg",
                # Overwrite any files that already exist.
                "-aoa",
                str(dmg_file.absolute()),
            ],
            cwd=dmg_extract_path.absolute(),
        )

    # Now extract the payloads from every ".pkg" file.
    for pkg_file in dmg_extract_path.glob("*Fonts.pkg"):
        # We will put every payload into unique sub-directories, since every
        # file is named "Payload~". 7zip has a "-so" option which could be used
        # to force the output to stdout instead, but then we'd have to redirect,
        # which is way more annoying than simply using separate folders.
        payload_extract_path = dmg_extract_path / f"{pkg_file.name}.payload"
        payload_extract_path.mkdir(mode=0o755, parents=True, exist_ok=True)

        run_ext(
            [
                "7z",
                "e",  # Extract.
                # Overwrite any files that already exist.
                "-aoa",
                str(pkg_file.absolute()),
                # Tell it the EXACT name of the file we want to extract.
                "Payload~",
            ],
            cwd=payload_extract_path.absolute(),
        )

    # Extract the actual font files from all of the payloads.
    # NOTE: Apple only uses ".otf" and ".ttf", but we add ".ttc" just in case.
    fonts_extract_path = dmg_extract_path / "fonts"
    fonts_extract_path.mkdir(mode=0o755, parents=True, exist_ok=True)
    for payload_file in dmg_extract_path.glob("*.payload/Payload~"):
        a = run_ext(
            [
                "7z",
                "e",  # Extract.
                # Only extract the font files, nothing else.
                # NOTE: This squashes the payload's internal "Library/Fonts" paths.
                r"-ir!*.otf",
                r"-ir!*.ttf",
                r"-ir!*.ttc",
                # Overwrite any files that already exist.
                "-aoa",
                str(payload_file.absolute()),
            ],
            cwd=fonts_extract_path.absolute(),
        )
    print("")

    # Apple ships legacy versions of some fonts, which are named things like
    # "Text" and "Display", and contain old-school font shapes that can't
    # dynamically morph to various scales. They are completely obsolete now,
    # and are only shipped for backwards compatibiblity with old Mac apps.
    # We only care about their modern, dynamically scaling fonts, so delete
    # all of the old garbage, to avoid confusing the users with legacy junk.
    # NOTE: The legacy fonts also waste a lot of disk space, since they need
    # to contain duplicate glyphs, whereas the modern, unified fonts are small.
    to_keep = []
    to_delete = []
    for f in fonts_extract_path.glob("*"):
        # Since Python's "glob" is very basic, we'll use a regex which is
        # equivalent to the following shell patterns:
        # ./SF-Pro-{Text,Display}*.otf
        # ./SF-Compact-{Text,Display}*.otf
        # ./NewYork{Small,Medium,Large,ExtraLarge}*.otf
        # NOTE: Glob files are in a jumbled order, so we'll use sorted lists
        # to display the delete/keep filenames in a nice order later.
        m = re.match(
            r"^(?:SF-(?:Pro|Compact)-(?:Text|Display)|NewYork(?:Small|Medium|Large|ExtraLarge)).*?\.otf$",
            f.name,
        )
        if m:
            to_delete.append(f)
        else:
            # Keep if it's a font file (case sensitive match).
            m = re.search(r"\.(?:otf|ttf|ttc)$", f.name)
            if m:
                to_keep.append(f)

    to_keep = sorted(to_keep)
    to_delete = sorted(to_delete)

    # Delete the useless legacy fonts.
    print("Deleting legacy Apple fonts...")
    deleted_size = 0
    for font_file in to_delete:
        print(f"* {font_file.name}")
        deleted_size += font_file.stat().st_size
        font_file.unlink(missing_ok=False)  # Throws if already missing.
    print(f"Deleted {bytes_to_mib(deleted_size)} of useless legacy fonts.\n")

    # As of this writing (May 2023), we now expect to have these font families:
    #
    # Modern (unified fonts):
    # * New York: NewYork.ttf, NewYorkItalic.ttf
    # * SF Arabic: SF-Arabic.ttf
    # * SF Arabic Rounded: SF-Arabic-Rounded.ttf
    # * SF Compact: SF-Compact-Italic.ttf, SF-Compact.ttf
    # * SF Pro: SF-Pro-Italic.ttf, SF-Pro.ttf
    #
    # Legacy (fonts that don't yet have a modern replacement):
    # * SF Compact Rounded: SF-Compact-Rounded-Black.otf, SF-Compact-Rounded-Bold.otf, SF-Compact-Rounded-Heavy.otf, SF-Compact-Rounded-Light.otf, SF-Compact-Rounded-Medium.otf, SF-Compact-Rounded-Regular.otf, SF-Compact-Rounded-Semibold.otf, SF-Compact-Rounded-Thin.otf, SF-Compact-Rounded-Ultralight.otf
    # * SF Mono: SF-Mono-Bold.otf, SF-Mono-BoldItalic.otf, SF-Mono-Heavy.otf, SF-Mono-HeavyItalic.otf, SF-Mono-Light.otf, SF-Mono-LightItalic.otf, SF-Mono-Medium.otf, SF-Mono-MediumItalic.otf, SF-Mono-Regular.otf, SF-Mono-RegularItalic.otf, SF-Mono-Semibold.otf, SF-Mono-SemiboldItalic.otf
    # * SF Pro Rounded: SF-Pro-Rounded-Black.otf, SF-Pro-Rounded-Bold.otf, SF-Pro-Rounded-Heavy.otf, SF-Pro-Rounded-Light.otf, SF-Pro-Rounded-Medium.otf, SF-Pro-Rounded-Regular.otf, SF-Pro-Rounded-Semibold.otf, SF-Pro-Rounded-Thin.otf, SF-Pro-Rounded-Ultralight.otf

    # Analyze font families and display information for the user.
    # NOTE: This is mostly meant to help devs with future analysis of families,
    # if Apple decides to modernize more fonts (so that we should delete more
    # legacy font packages above).
    print("Analyzing Apple font packages...")
    font_families = {}
    for font_file in to_keep:
        font_family = get_font_family(font_file)
        if font_family not in font_families:
            font_families[font_family] = []
        font_families[font_family].append(font_file)

    for font_family in sorted(font_families.keys()):
        plain_names = [x.name for x in font_families[font_family]]
        print(f"* {font_family}: {', '.join(plain_names)}")
    print("")

    # Create the actual font output directory.
    target_path = create_font_output("apple-fonts")

    # Copy all fonts to the correct output directories, sorted by family name.
    print("Copying all Apple fonts...")
    final_size = 0
    for font_family in sorted(font_families.keys()):
        for font_file in font_families[font_family]:
            target_file = copy_font(font_file, target_path)
            final_size += target_file.stat().st_size

    print(f"\nOutput font size (Apple): {bytes_to_mib(final_size)}.\n")

    # Clean up temporary files.
    rmtree(dmg_extract_path)

    return final_size


# Licensing.
print("***")
print(
    "WARNING: BY USING THIS SOFTWARE, YOU AGREE THAT YOU HAVE LICENSES FOR ALL FONTS AND THAT YOU ARE USING THEM ON THEIR INTENDED PLATFORMS, IN ACCORDANCE WITH THEIR LICENSING AGREEMENTS."
)
print("***\n")

# Check external dependencies.
deps = ["wget", "7z", "fc-scan"]
for dep in deps:
    if not command_exists(dep):
        print(
            f'Missing external dependency "{dep}". Please install it and ensure that it exists in your PATH environment.'
        )
        exit(1)

# Build the font collections.
time_start = time.time()

rmtree(OUTPUT_PATH)  # Remove any leftover files.
output_size = 0
output_size += process_microsoft()
output_size += process_apple()
rmtree(TEMP_PATH)
print(f"Output font size (Total): {bytes_to_mib(output_size)}.\n")

time_elapsed = int(time.time() - time_start)

print(f"Build finished in {datetime.timedelta(seconds=time_elapsed)} (H:M:S).")
