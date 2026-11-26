# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "rclone-server"
name: "Rclone server for data management"
category: "UTILITIES"
tags:
- file-management
- interactive
---
This application will start an [Rclone](https://rclone.org/) WebDAV or SFTP server that serves data from the mounted Fuzzball volumes and allows you to access, browse, upload, and download files from our Fuzzball persistent storage volumes using any compatible client.

The server runs on the specified port (default 8080).

## Choosing the volumes to serve

`Volumes` is a comma-separated list. Give each persistent volume by its name,
or use `ephemeral` for a scratch volume that is discarded when the workflow ends.
Each volume is served as `/<name>`, or at the path you give after a colon:

```
fuzzball workflow catalog start "Rclone server for data management" --values Volumes=my-data:/projects
```

In-line `--values` splits on commas, so to serve several volumes set `Volumes`
(for example `my-data,results:/runs/latest`) in a values file instead.

The default, `ephemeral:data`, serves an empty scratch volume as `/data`: files
you upload there are lost when the workflow stops. Set `Volumes` to the name of a
persistent volume to serve data you keep.

- **A volume name is resolved across the organization.** Fuzzball searches every
  provisioner you can reach for a volume of that name and binds the single
  match, so a name cannot pin a provisioner. Give the volume a name that is
  unique across provisioners: two matches fail the submit.
- **`ephemeral` always means a scratch volume**, so a persistent volume named
  `ephemeral` cannot be served by this entry.
- **The older `volume://<scope>/<class>[:path]` references are no longer
  accepted.** Give the volume's name instead.

To access the server, you'll need to use port-forwarding:
```
fuzzball workflow port-forward <workflow-id> <protocol> <port>:<port>
```

The full command will be included in the log for convenient copy-and-paste.

Then you can connect to the port on localhost with your client of choice.

## Client Tools for File Transfers

In addition to using rclone itself as a client tool, there are many graphical and
command-line clients you can use for transferring files to/from the rclone-based
SFTP/WebDAV server in Fuzzball.

### WebDAV Clients
- **[Cyberduck](https://cyberduck.io/)** - Cross-platform file transfer client with WebDAV support
- **[WinSCP](https://winscp.net/)** - Windows client with WebDAV support
- **Finder** (macOS) - Native WebDAV support via "Connect to Server"
- **Files** (Windows) - Native WebDAV support via "Map network drive"
- **Nautilus/Dolphin** (Linux) - File managers with built-in WebDAV support
- **WebDAV clients in web browsers** - Many browsers can mount WebDAV directly

### SFTP Clients
- **[Cyberduck](https://cyberduck.io/)** - Cross-platform with excellent SFTP support
- **[WinSCP](https://winscp.net/)** - Popular Windows SFTP client
- **[FileZilla](https://filezilla-project.org/)** - Free, cross-platform FTP/SFTP client
- **OpenSSH client** - Command-line SFTP access (`sftp user@localhost -P port`)
- **[Termius](https://termius.com/)** - Modern SSH/SFTP client with GUI
- **Files** (macOS/iOS) - Native SFTP support

Notes:
- Transfer speeds may not be optimal for very large transfers.
- The server job will run until it hits the timeout or you terminate it
  manually.
