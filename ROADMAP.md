# Roadmap

Planned features for Route Builder, ordered by complexity. No strict timeline — features will be added as time permits.

**Contributions are welcome!** If you'd like to help with any of these features, feel free to open an issue or submit a pull request.

---

## Easy

### Import from CSV/Excel
Load coordinates directly from a file. CSV parsing is straightforward (comma/semicolon/tab separators, dot/comma decimal). Excel support may require `openpyxl`.

**Why:** Avoid manual entry into the Spreadsheet. Useful for large routes.

### Trajectory cloning
Duplicate an existing route with or without offset. Useful for creating parallel routes or symmetric layouts.

**Why:** Fast duplication instead of rebuilding the whole route.

### User presets
Save and reuse profile sets (e.g., "Pipe DN100, wall 5 mm", "Box 40x40x3").

**Why:** Avoid re-entering the same profile settings every time.

### Additional export formats
Add STL, IGES, OBJ export options alongside the existing STEP export.

**Why:** STL for 3D printing, IGES for other CAD systems.

---

## Medium

### Attachment to arbitrary points
Parametric position on an edge or face (e.g., 20% along an edge, or a specific U/V coordinate on a face).

**Why:** Current attachment only supports vertices, edge midpoints, and face centers. This limits precision.

### Diagonal segments
Create and edit diagonal segments directly in the Builder and Vectors tabs, with dynamic vector display in 3D space.

**Why:** While diagonal coordinates can be entered manually in the Spreadsheet, there is no interactive UI for it. The Builder should support arbitrary directions with a live phantom preview.

**Technical note:** The overlap check is currently designed for parallel segments. For arbitrary directions, full 3D intersection checks will be required.

### Point-to-point segments
Connect two existing points (vertices or route ends) with a straight segment. Optionally close the loop.

**Why:** Useful for closing contours, joining two routes, or attaching a route end to a vertex of a body.

**Use cases:**
- Closing a loop (route end → route start)
- Joining two routes (route A end → route B start)
- Attaching to a vertex of another part

### Table-driven profiles
Define profile dimensions in a Spreadsheet. The profile is built from these dimensions.

**Why:** Current profiles are limited to hard-coded standards (DN15–DN500, 20–100 mm square, etc.). Table-driven profiles allow any custom profile.

**Challenge:** Different profile types (circle, square, rectangle) require different table structures. Validation will be needed.

---

## Notes

- **No strict timeline.** Features will be added as time permits.
- **Priority may shift** based on community feedback.
- **If you'd like to contribute** — pick any "Easy" feature and open a PR. Or open an issue to discuss a "Medium" one first.
- **Not in Addon Manager yet** — the workbench will be submitted after community feedback.

---

*Last updated: 2026-09-17*