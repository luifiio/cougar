#!/usr/bin/env bash
# Simple scripted COLMAP photogrammetry pipeline (sparse -> dense -> fused point cloud)
# Usage: ./run_photogrammetry.sh /absolute/path/to/images /absolute/path/to/output
# Requires COLMAP installed and available on PATH. For meshing and texturing you can use OpenMVS or Meshroom.

set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 /path/to/images /path/to/output"
  exit 1
fi

IMAGES_DIR="$1"
OUT_DIR="$2"

mkdir -p "$OUT_DIR"
cd "$OUT_DIR"

DB="database.db"
SPARSE_DIR="sparse"
DENSE_DIR="dense"

echo "Using images: $IMAGES_DIR"
echo "Output: $OUT_DIR"

echo "--> Step 1: Feature extraction"
colmap feature_extractor --database_path "$DB" --image_path "$IMAGES_DIR"

echo "--> Step 2: Exhaustive matching"
colmap exhaustive_matcher --database_path "$DB"

echo "--> Step 3: Sparse reconstruction (mapping)"
mkdir -p "$SPARSE_DIR"
colmap mapper --database_path "$DB" --image_path "$IMAGES_DIR" --output_path "$SPARSE_DIR"

echo "--> Step 4: Convert the best sparse model to dense workspace (image undistorter)"
# Assumes the first model output (0) is the desired one
colmap image_undistorter --image_path "$IMAGES_DIR" --input_path "$SPARSE_DIR/0" --output_path "$DENSE_DIR" --output_type COLMAP

echo "--> Step 5: PatchMatch stereo (dense reconstruction)"
colmap patch_match_stereo --workspace_path "$DENSE_DIR" --PatchMatchStereo.geom_consistency true

echo "--> Step 6: Stereo fusion (fuse depth maps to a single dense point cloud)"
colmap stereo_fusion --workspace_path "$DENSE_DIR" --output_path "$DENSE_DIR/fused.ply"

echo "Done. Results written to: $DENSE_DIR/fused.ply"
echo "Next steps:"
echo " - Inspect the point cloud in Meshlab or CloudCompare"
echo " - Use OpenMVS or Meshroom to reconstruct a mesh + texture from the COLMAP dense output"
echo " - For OpenMVS, you can import the COLMAP output and run DensifyPointCloud, ReconstructMesh, RefineMesh, TextureMesh"

echo "Example OpenMVS steps (not scripted here, see README-photogrammetry.md):"
echo "  DensifyPointCloud scene.mvs"
echo "  ReconstructMesh scene_dense.mvs"
echo "  RefineMesh scene_dense_mesh.mvs"
echo "  TextureMesh scene_dense_mesh_refine.mvs"

exit 0
