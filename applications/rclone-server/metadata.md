# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "rclone-server"
name: "Rclone server for data management"
category: "UTILITIES"
---
This application will start an [Rclone](https://rclone.org/) WebDAV or SFTP server that serves data from the mounted Fuzzball volumes and allows you to access, browse, upload, and download files from our Fuzzball persistent storage volumes using any compatible client.

The server runs on the specified port (default 8080).

To access the server, you'll need to use port-forwarding:
```
fuzzball workflow port-forward <workflow-id> <protocol> <port>:<port>
```

The full command will be included in the log for convenient copy-and-paste.

Then you can connect to the port on localhost with your client of choice.

Notes:
- Transfer speeds may not be optimal for very large transfers.
- The server job will run until it hits the timeout or you terminate it
  manually.
