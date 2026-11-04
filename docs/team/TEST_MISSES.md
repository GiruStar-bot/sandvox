# 見逃しの帳面（D116）

取り込みの確かめを省いた分（同じ土台なら DIGEST だけ・土台がずれたら affected＋DIGEST）を、夜の一括（`tools/test/nightly.sh`）が拾ったかを残す。

- 夜の一括で落ちた試験は、その日の最初の作業で直す（ほかの作業より先）。
- 落ちたのが取り込みの時に回らなかった試験なら「見逃し」。その試験を tiers.json の map か smoke に足して、同じ形の見逃しを塞ぐ。下の表の「塞いだ」に書く。
- 見逃しが1週間に2回を越えたら、省き方（D116）を見直す。
- `tools/run_tests.sh --tier affected` が `UNMAPPED <file>` を出したら、その道を map に足す（出ている間は smoke に落ちて回る）。

| 日 | 範囲 | full | DIGEST | 落ちた試験 | 見逃しか・塞いだ |
|---|---|---|---|---|---|
| 2026-10-08 | ?..bd6e8c6 | tests 96: pass 94, warn 0, fail 1, known 1 | checks passed 3543, failed 2 | leaked objects 0 | total 2934.8 s | STRICT_LEAKS | time budgets: report only | DIGEST off ok ef9f23a3b05fc4f202cf90ea63027395 DIGEST decisions ok 1d69664b06993ff160da9f283daeb173 DIGEST ties ok 8081892b6cf31bc90d20ad3bdfbfc75f  | test_determinism が 600 秒で切れた（取り合いでの遅れ。1本だけで 417 秒・11/11）。見逃しでなく枠の時間。nightly.sh に TEST_TIMEOUT 1500 を足して塞いだ。test_org_forms は既知 |
| 2026-10-09 | bd6e8c6..5a238d1 | tests 100: pass 99, warn 0, fail 0, known 1 | checks passed 3664, failed 2 | leaked objects 0 | total 1701.0 s | STRICT_LEAKS | time budgets: report only | DIGEST off ok ef9f23a3b05fc4f202cf90ea63027395 DIGEST decisions ok 7fd5c5a714b3d3f05edd9c27baf348cb DIGEST ties ok 8081892b6cf31bc90d20ad3bdfbfc75f  | 落ち無し（test_org_forms は既知）。見逃し無し |
| 2026-10-10 | 5a238d1..7d1100f | tests 105: pass 103, warn 0, fail 1, known 1 | checks passed 3805, failed 3 | leaked objects 0 | total 4730.8 s | STRICT_LEAKS | time budgets: report only | DIGEST off ok ef9f23a3b05fc4f202cf90ea63027395 DIGEST decisions ok 7fd5c5a714b3d3f05edd9c27baf348cb DIGEST ties ok 8081892b6cf31bc90d20ad3bdfbfc75f  | test_art_file が落ちた: art3 の和の絵28枚の .import が process/fix_alpha_border=true で、取り込むと画素が元の .png と変わる（world/pixel/assets の他の絵は false）。**見逃し**: art3 は土台が同じで integrate_check の「DIGEST だけ」の道を通り、作業者も test_art_file を回していなかった。塞いだ（3e3d953）: 28枚を false に直し test_art_file 7/7、integrate_check.sh は土台が同じでも affected を回す（map の world/pixel/ は既に test_art_file を含む）。test_org_forms は既知 |
