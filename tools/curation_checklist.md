MX-5 (NB / Mk2) Photogrammetry Curation Checklist
-------------------------------------------------

Use this checklist when photographing your car and preparing images for the photogrammetry pipeline.

1) General shooting guidelines
- Shoot 40–120 images if possible. More images = better coverage.
- Walk around the car in a few passes:
  - Low pass (~knee height) covering full 360°
  - Mid pass (about waist height)
  - High pass (higher angles for roof/bonnet if safe)
- Keep consistent spacing and overlap — aim for 60–80% overlap between consecutive shots.

2) Key viewpoints to capture
- Front 3/4 (left & right)
- Side profiles (left & right)
- Rear 3/4 (left & right)
- Roof/top shots (if possible)
- Underside & wheel arches (optional, useful if you want underbody detail)
- Interior shots (if you want interior reconstruction) — note interior photogrammetry is harder due to low light.

3) Camera settings & environment
- Use a low ISO and steady shutter (tripod if needed). Higher resolution images help.
- Overcast days reduce harsh shadows and reflections — ideal.
- Avoid direct sunlight and strong reflections where possible. If you must shoot in sunlight, use polarizing filter to reduce glare.

4) Avoid these problems
- Highly reflective panels (windows, chrome) can cause artifacts — try to get some shots with polariser or slightly different angles.
- Large occluders (people, other cars) in many photos confuse reconstruction — remove extra objects or mask them out.
- Very similar but different vehicles (different years/trim) — ensure all photos are of the exact car you want to reconstruct.

5) Prepare images for processing
- Remove duplicates and extremely blurred photos.
- Optionally downscale very large images (e.g., >20MP) if memory is limited — but keep resolution reasonable.
- Keep filenames sequential for convenience (001.jpg, 002.jpg...).

6) Manual curation step
- After initial run, inspect `fused.ply` in MeshLab. If holes or missing sections appear, capture more photos focusing on those areas and re-run the pipeline.

7) Extras for better texture
- Shoot some close-ups of distinctive panels (emblems, grille) to help texture detail.

Good luck — if you want, I can add an OpenMVS helper script next to automate mesh reconstruction and texturing from the COLMAP outputs.
