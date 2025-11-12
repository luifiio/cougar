Photogrammetry starter (COLMAP)
=================================

This folder contains a small starter for running photogrammetry locally on your own photos. It's tailored for a one-off portfolio project: reconstructing your Mazda MX‑5 (NB / Mk2) into a textured 3D mesh.

What you'll get
- A fused dense point cloud (PLY) from COLMAP after running the provided script.
- Guidance and next steps to convert the point cloud into a mesh and texture it (OpenMVS or Meshroom + Blender recommended).

Prerequisites
- macOS with Homebrew is assumed (instructions below are macOS-centric). Adjust for Linux/Windows as needed.
- COLMAP installed and available on PATH. Install via Homebrew (may require additional dependencies):

  brew install colmap

- (Optional) Meshroom (AliceVision) if you prefer a GUI pipeline: https://github.com/alicevision/meshroom
- (Optional) OpenMVS for meshing and texturing (build from source or use prebuilt binaries).
- Blender for cleanup and exporting glTF/OBJ: https://www.blender.org/download/

Quick start
1. Copy your MX-5 photos into a folder, e.g. `/Users/you/photos/mx5/`.
   - Prefer JPGs, consistent resolution is helpful.
2. Run the script from the repo:

```bash
chmod +x tools/run_photogrammetry.sh
./tools/run_photogrammetry.sh /absolute/path/to/images /absolute/path/to/output
```

3. Open the produced `dense/fused.ply` in MeshLab or CloudCompare to inspect the point cloud.
4. To produce a mesh + texture: use OpenMVS or Meshroom. Meshroom is easiest for beginners (drag images into the GUI and run the pipeline).

Notes & tips
- If COLMAP fails to match many images, review and cull photos that have poor overlap or heavy occlusions. The `tools/curation_checklist.md` explains good/bad shots.
- For best texture consistency, shoot in consistent lighting (overcast days are great). Avoid reflections where possible.
- You can decimate or retopologize the final mesh in Blender for better performance in a web viewer.

Legal note
- You're using your own photos, so you own the rights to them and can safely publish the resulting mesh in a portfolio.

Next steps (optional)
- I can add an OpenMVS helper script to convert COLMAP output into a textured mesh if you want a more automated pipeline.
- I can also add a small glTF viewer page to the repo and instructions to export the mesh into glTF for web embedding.
