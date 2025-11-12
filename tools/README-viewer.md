Adding a web viewer (model-viewer)
=================================

This page (`viewer.html`) uses `<model-viewer>` to embed a glTF/GLB model into your site. Below are quick instructions and sources for non-copyright placeholder models.

Where to put your files
- Place your exported GLB at: `assets/models/mx5.glb`
- Place a poster image (JPG/WEBP) for quick loading previews at: `assets/models/mx5-poster.jpg`
- (Optional) Provide a USDZ for iOS AR at `assets/models/mx5.usdz`.

Sample CC0 / public domain 3D models
- Sketchfab (filter "Downloadable" and license to CC0): https://sketchfab.com
- Poly (archived) and other repositories — search for "CC0 car glb" or "public domain car model".
- modelviewer.dev shared assets (demo): https://modelviewer.dev/shared-assets/models/Astronaut.glb
- NASA / public-domain assets are safe for placeholders but are not cars.

Best placeholder car sources (license-check required)
- Sketchfab: search and filter by license. Many creators use CC-BY or CC0; always check the model page for license details.
- Poly Haven / 3D model sites: look for CC0 or permissive licenses.

Poster tip
- Create a poster by rendering a single frame in Blender (800–1600px wide) or use a screenshot of the model viewer.
- Save as JPG or WEBP and place in `assets/models/mx5-poster.jpg`.

If you want, I can add a small script that converts an exported OBJ/GLTF into a glb and runs `gltfpack` for Draco compression.
