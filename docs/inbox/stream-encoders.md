# inbox: stream-encoders (out-of-slice observations)

* `Global/PartitionTable` entry `id_b` == the FIRST `DocumentIncrementTable`
  record's `id_pair.a` in 6/6 files (824/596/776/989/556/2654) — the workset
  entry stores the EpisodeId at which the current increment history begins.
  Whoever owns PartitionTable/worksharing semantics may want it.
* DIT record semantics still open (documented as hypotheses in
  docs/streams/13-stream-encoders.md §5/§8): counters[0..9] progression is
  mechanical (idx 1..9 = +1 per save, idx 7 gated by flag, 160/160), but the
  meaning of each counter, of `hdr5`, and of the extra `(key, count)` pairs
  appended to superseded records (last pair == (own sequence, 0) only 88/160)
  is unresolved. On flag=1 saves the `(-1, X)` value ≈ the partition's
  element-record count (racbasic 85,814 == seq-102 record count) — worth a
  cross-check by whoever owns partitions.
* `Contents` class-stream prologue `class_ref` (racbasic 183, racadv 213,
  rme 424, rstbasic 178, rstadv 264, dach 430) is per-document and not a
  schema class id; the encoder just carries it through the model.
* `frame_stream()` in stream_encoders defers to `rvt.ecc.page_trailer(page)`
  via `from .ecc import page_trailer` — that is the contract this slice
  assumes from the ECC fleet (zero-byte placeholder + `ecc_valid=False`
  until the module exists).
