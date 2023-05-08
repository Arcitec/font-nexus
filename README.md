# Font-Nexus

Helps application developers install all necessary fonts when writing cross-platform applications, to simplify the debugging and development process.


## Dependencies

- Python 3.10 or higher.
- The following external binaries:
- `rsync`
- `wget`
- `7z` (usually from packages such as `p7zip` or `p7zip-plugins`).
- `fc-scan` and `fc-cache` (from the `fontconfig` package).
- `restorecon` (optional; for updating SELinux labels, and will only be used if found).


### Installing all dependencies on Fedora

This example is for Fedora, which already has fontconfig and SELinux (optional) installed by default.

```sh
sudo dnf -y install p7zip p7zip-plugins wget rsync
```

The packages are usually named very similar things on other distros.


## Usage

Simply run the following command to perform a clean (re-)build and install everything.

```sh
./font-nexus.sh -b -i
```

Tip: If you already have a local build, it's faster to skip the `-b` flag to immediately install your existing local build instead of re-building everything.

For a list of all arguments, run the following command instead.

```sh
./font-nexus.sh -h
```

## Advanced Usage

You can change which Windows font groups will be installed. By default, we save hundreds of megabytes of disk space by skipping all non-Western fonts. You can customize the selected groups by providing a comma-separated environment variable, as follows:

```sh
env WINDOWS_FONT_GROUPS="win11,win11_other,win11_japanese" ./font-nexus.sh -b
```

It's recommended that you always install the default, main groups (the ones that are installed if you don't provide any environment variable). However, your choices will of course depend on your application development needs, such as if you're developing an application for an Asian audience.

To see all of the available groups, simply look at the output of the above command, and look at the "Disabled font groups" near the top of the results, for a list of groups that you can add to your system. Keep in mind that you have to specify every group manually, even the "defaults", if you use this manual group override feature.

Good luck with your application development!
