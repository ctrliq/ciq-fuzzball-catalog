---
id: blender-parallel-render
name: Blender Render Pipeline
category: MODELING
featured: true
tags:
  - blender
  - rendering
  - ffmpeg
  - parallel
---
This workflow provides a complete pipeline for rendering Blender animations in parallel.

It performs the following steps:
1. **Setup**: Downloads and extracts a Blender project zip file.
2. **Render**: Uses a Fuzzball Task Array to render individual frames across multiple nodes/cores simultaneously.
3. **Assemble**: Uses FFmpeg to combine the rendered frames into a single MP4 video.
4. **Egress**: (Optional) Automatically uploads the final video to a specified S3 bucket if a destination is provided.

You can customize the project URL, the specific `.blend` file to render, the frame range, and the hardware resources allocated to the render jobs.