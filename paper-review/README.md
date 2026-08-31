# VANAD Paper — Review Desk artifact

`VANAD_WACV2027_review.html` is a self-contained review interface for the WACV 2027
submission *"VANAD: Named-Vessel-Aware Aneurysm Detection and Segmentation in TOF-MRA"*.
It was generated from the original `.docx` so the paper can be reviewed and then edited
from a separate Claude session.

## Layout

- **Left (70%)** — the paper reproduced faithfully (title, abstract, numbered
  sections, both figures, both tables, references). The body text is **not** modified.
- **Right (30%)** — a comment rail. Hover any section heading, figure, or table and
  click **＋ 의견** to attach an opinion there; use **＋ 새 의견** for a general note.

Comments autosave to the browser (`localStorage`). Nothing on the left is editable here.

## Cross-session handoff

The page declares the `artifact` runtime capability, so **Claude로 보내기 (Publish)**
bakes the current comments into the published artifact as a machine-readable JSON island:

```html
<script type="application/json" id="comments-data">
{ "schema":"vanad-review/1", "publishedAt":"…", "comments":[
    { "id","anchor","anchorLabel","text","createdAt","updatedAt" } ] }
</script>
```

`anchor` is the element `id` in the paper body a comment refers to (`general` = whole
paper). A second Claude session opens the artifact URL, reads that JSON, and edits the
paper body at each anchored location — then republishes to the same URL.

Fallbacks when publishing isn't available (e.g. a preview context): **복사** copies all
comments as Markdown, and **내보내기** saves them as a `.md` file (via the `downloads`
capability).

## Regenerating

The HTML embeds the two figures as optimized base64 PNGs. To rebuild from the source
`.docx`, re-extract the text/tables/figures and re-inject the images; see the commit
that introduced this folder for the extraction steps.
