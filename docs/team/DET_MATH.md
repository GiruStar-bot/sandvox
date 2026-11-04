# 決定の数学（DET_MATH）

## なぜ
持ち主の Windows の PC（i5-7200U、Godot 4.7.2 公式、拡張の .dll なし＝GDScript で計算）で、同じ種なのに Linux と答えが違った（2026-10-08）。
- 10年・種42 の DIGEST_SIM: Windows 旗切 `e978b99f…`（Linux `a6faebf1…`）、decisions `7695bba8…`（Linux `f11e2cf3…`）、ties `9e739ce0…`（Linux `55d952d5…`）。1年 `c0792673…`（Linux `310502d3…`）。
- self_check の GDScript の答えの md5（`plan_utilities` は exp・pow を使う）: Windows `d15f3d41…`、Linux `0330d45c…`。
- 同じ PC の中では毎回同じ。

見立て: Godot の `exp`・`pow`・`log`・`sin`・`cos`・`atan2` と `randfn`（中で log・cos）は OS の数学の庫（Linux は glibc、Windows は CRT／mingw の libmingwex）を呼び、最後のビットが違う。C++ の拡張も、Linux は glibc、Windows の .dll は libmingwex を使う。
持ち主の目的（D120）は、同じ始めを種を変えて回して必然性を測ること。機械によって未来が変わると、持ち主の PC・ほかの遊び手と同じ世界線を比べられない。

## 形
- GDScript の正本 `sim/api/det_math.gd`（`class_name DetMath`、静的関数）。C++ の双子 `native/the_world_native/src/det_math.h`（`namespace detm`、同じ式・同じ順）。
- 使うのは、IEEE 754 で答えが1つに決まる演算（足し算・引き算・掛け算・割り算・`sqrt`・`floor`・`fabs`）と、整数・ビットの操作だけ。x86-64 の SSE2 では OS によらず同じ。
- 式は fdlibm（Sun、1993）: `exp`（e_exp）・`log`（e_log）・`sin`・`cos`（π/2 で3段の Cody–Waite の縮め＋FreeBSD 版の k_sin・k_cos）・`atan`・`atan2`（s_atan・e_atan2）。`pow(x, y)` は `exp(y・log x)`（y = 0・1・2・−1・0.5 は別の道）。
- 係数・定数は整数のビットで書く（GDScript は `_f(0x…)`、C++ は `__builtin_bit_cast`）。10進の読みの違いに頼らない。負の係数は正のビットから作って符号を変える（GDScript の 0x8000… 以上の字は int64 を溢れるため）。
- `DetMath.randfn(rng, mean, sd)`: `RandomNumberGenerator.randf()` を2つ引き（整数の PCG から作るので OS によらず同じ）、Box–Muller を `DetMath.log`・`cos`・`sqrt` で作る。
- `DetMath.angle_to(v, u)`・`DetMath.rotated(v, a)`: `Vector2.angle_to`・`rotated`（中で atan2f・sinf・cosf）の代わり。
- C++ のコンパイルは `-ffp-contract=off`（掛けて足すを1命令にまとめない。FMA で丸めが変わらない）。`-ffast-math` は使わない。SConstruct で Linux の g++ と mingw の両方に効く。

## 決まり（作業者向け）
- **sim の答えに入る計算で `exp`・`log`・`pow`・`sin`・`cos`・`atan2`・`randfn`・`Vector2.angle_to`・`rotated` を直接使わない。`DetMath.*`（C++ は `detm::*`）を使う。**
- `sqrt`・`floor`・`ceil`・`round`・`absf`・`fmod`・`fposmod`・`snapped`・`lerp`・`smoothstep`・`clampf` はそのままでよい（IEEE で答えが1つに決まるか、足し算と掛け算だけ）。
- 画面だけの計算（絵の揺れ・カメラ）、試験・probe・bench の中の sim の答えに入らない計算はそのままでよい。
- C++ の核に数学を足す時は `det_math.h` を使い、GDScript の双子は `DetMath` を使う（parity は `native/test_native_parity.gd`）。

## 線（回す前に決める）
| 線 | 値 | 確かめ |
|---|---|---|
| 精度 | 今の値（Godot の組み込み＝この箱の glibc）との相対差が、`exp`・`log`・`sin`・`cos`・`atan2` で 1e-15 以下、`pow` で 1e-12 以下（ふつうの範囲。表は下） | `sim/api/test_det_math.gd` |
| 決まった答え | 定数の点の答えのビットが試験に書いた値と同じ（OS・C++ か GDScript かによらず） | `sim/api/test_det_math.gd`、`native/test_native_parity.gd` |
| parity | GDScript と C++ の `detm` がビット単位で同じ（種 42 の乱数の入力 各 20,000 件 ＋ 端の値） | `native/test_native_parity.gd` |
| 重さの決め（メイン、2026-10-08） | Windows の配布には .dll を必ず入れ、GDScript だけの道は確かめ用と割り切る。`--gdscript` の心の層の +27% は許す（GDScript の決定の数学は組み込みの約10倍重く、2回の直しで線に届かなかったため） | 速さの直しはこれ以上しない |
| 重さ | `sim/people/psyche/bench_psyche.gd -- --people 2000 --days 200 --on` の 1日あたりの ms が、C++ と `--gdscript` のそれぞれで前の +10% まで（`GODOT_EXCLUSIVE=1` で1本だけ） | 下の表 |
| 置き換え | `sim/`・`world/pixel/` の sim の層・`tools/self_check/` の中で、上の関数を直接呼ぶ所が 0（試験・probe・bench・画面だけの所は除く） | `grep`（下の手順） |
| 試験 | `tools/run_tests.sh --tier full -j3` が前と同じ通り方（既知の落ちのほかに落ちが増えない）、SOA_MISMATCH 0、`world/pixel/test_determinism.gd` が通る | |
| DIGEST | 旗切・`--decisions on`・`--ties on`（10年・種42）と1年の既定の世界の新しい値が、C++ と `--gdscript` で同じ | `tools/test/digests.sh`、probe の `--gdscript` |

## DIGEST の作り直しの手順
1. `DetMath` と `detm` に置き換え、.so を作り直す（`native/third_party` を worktree へ写して scons）。
2. `GODOT=tools/godot1.sh` で `world/pixel/probe_wanderer_years.gd -- --years 10 --seed 42`（旗切）・`--decisions on`・`--ties on`、`--years 1` を、C++ と `--gdscript` で回す。
3. C++ と `--gdscript` が同じなら、その値を `tools/test/digests.json`（off・decisions・ties）と `tools/self_check/self_check.gd` の `EXPECTED_SIM`（1年・10年）に書く。`EXPECTED_KERNEL_MD5` は self_check の答え合わせの GDScript の md5（DetMath を使う形）を書く。
4. 同じコミットで DECISIONS.md に1行（基準を替えたこと・なぜ）。
5. 持ち主の Windows で self_check（`-- --self-check`、`--self-check-gdscript`、`--self-check-years 10`）を回してもらい、同じ値になるかを見る（この箱では Windows を回せない）。

## 結果（2026-10-08、この箱、土台 1bd5991）

### 置き換えた数
- GDScript: 275 か所・42 ファイル（`exp`・`log`・`pow`・`sin`・`cos` 240、`randfn` 32、`angle_to` 2、`rotated` 1）。`sim/`（試験・probe・bench を除く）と `world/pixel/village_spec.gd`・`session/village_craft_bridge.gd`・`session/player_session.gd`（町の形・作業場の置き場・始まりの場所。sim に入る）。画面だけの所（絵の揺れ・カメラ・夜の灯）と `world/flat/`（平らな世界、別の遊び方）は残した。
- C++: 87 か所・3 ファイル（`std::exp` 65、`std::pow` 19、`std::log` 3）。.so が呼ぶ数学の庫は `floor`・`sqrt`・`ldexpf`（どれも IEEE で答えが1つ）だけになった（`nm -D`）。
- 置き換えの後、上の範囲で組み込みの数学を直接呼ぶ所は 0（注釈を除く）。

### 精度（`sim/api/test_det_math.gd`、Godot の組み込み＝この箱の glibc と比べる。各 20,000 件）
| 関数と範囲 | 組み込みと同じビット | 相対差の最大 |
|---|---|---|
| exp [−50, 50] | 90.2% | 2.19e-16 |
| exp [−700, 700] | 90.2% | 2.18e-16 |
| log (0, 10] | 93.6% | 2.22e-16 |
| log [0.5, 2] | 92.4% | 2.22e-16 |
| pow x∈(0, 10]・y∈[−5, 5] | 36.6% | 2.34e-15 |
| pow δ∈[0.9, 1)・整数 t∈0..240 | 23.2% | 3.41e-15 |
| pow x∈[0.5, 2]・y∈[−1000, 1000] | 3.3% | 1.08e-13 |
| sin・cos [−7, 7] | 85.0%・84.4% | 2.22e-16 |
| sin・cos [−1e5, 1e5] | 84.9%・84.3% | 2.22e-16 |
| atan2 [−10, 10]² | 82.0% | 2.22e-16 |
| atan [−100, 100] | 98.6% | 2.03e-16 |

線（exp・log・sin・cos・atan2 は 1e-15、pow は 1e-12）の中。`tools/det_math/det_math_ref.py`（同じ式の Python の写し）で 200,000 件ずつ回しても同じ（pow の最大 1.23e-13）。
決まった点 122 個（端の値を含む）の答えのビットは、Python の写しで作った表と同じ（試験の FIXED）。

### parity（`native/test_native_parity.gd`、68 項目すべて通る）
- `det_math`: exp・log・pow・sin・cos・atan2・atan のそれぞれ 20,625 件（種 42 の乱数 20,000 ＋ 端の値 25×25）で、GDScript と C++ がビットまで同じ。
- `rng_randfn`（C++）と `DetMath.randfn`: 500 種 × 16 個がビットまで同じ。
- 前からある核（plan_utilities・leave_utilities・tool_gain・ask・give・monthly・LOD・国の核）も全部一致のまま。
- Windows の .dll（`tools/native/build.sh windows both`）は通る。.dll が読む数学の関数も `detm` の中だけ（mingw の exp・pow は呼ばない）。Windows の上で回すのは持ち主の self_check。

### 新しい DIGEST の基準（種 42、`probe_wanderer_years`。C++ と `--gdscript`（国と LOD の核も GDScript）で同じ。SOA_MISMATCH 0）
| 回し | 前 | 後 |
|---|---|---|
| 10年 旗切 | a6faebf199a5d5fe903b76ff95ee37c5 | ef9f23a3b05fc4f202cf90ea63027395 |
| 10年 `--decisions on` | f11e2cf3e3a262aaf75122c12d617711 | 5fbc2d5d2dc7b55962cc14c51df19ca4 |
| 10年 `--ties on` | 55d952d5636eee26d1371aa0cc9a7f65 | 8081892b6cf31bc90d20ad3bdfbfc75f |
| 1年（既定の世界） | 310502d30a2942c59ab845068e0e7c73 | 3a20fc58952ec902e28c6bcfcac1287a |
| self_check の GDScript の答えの md5 | 0330d45c968f20b36615581522b0d6a3 | c3c1358c27ad57a48fded43b2aac7c02 |

本流（心の判断を既定で入 D136・家畜・始めの制度の続き）を取り込んだ後の基準: 旗切（`--decisions off`）`ef9f23a3…`（同じ）、decisions `1d69664b06993ff160da9f283daeb173`（本流の決定の数学の前は `ba07f74a…`）、ties（`--decisions off --ties on`）`8081892b…`（同じ）、1年（既定＝判断入）`7552e411a99523df666496a3497c57b7`（前 `2e2e10a2…`）、self_check の10年は decisions と同じ。md5 は `c3c1358c…` のまま。

本流の D138・D139（文書だけ）を取り込んだ後（土台 ef501d5）も、上の5つの値は C++ と `--gdscript` で同じで変わらない（SOA_MISMATCH 0、self_check の1年・C++ と10年・`--self-check-gdscript` は「結果: OK」）。`tools/run_tests.sh --tier affected origin/main-szra3m -j3`（93本）: 合格 92、KNOWN 1（`test_org_forms`）、落ち 0。
結婚した日に2人の「相手」の欠けを 0 にする直し（5bc1794、`psyche.wed`）は決定の数学ではなく本流の心の層の抜けの直し。月の式の番の間に結婚した人が最大30日「相手が欲しい」まま決めていた。本流の世界線ではたまたま `test_needs` の終わりの日にその人が居ず、決定の数学の世界線で居たので見つかった。別のコミットのまま置き、本流へは単独で拾える。

世界の形は前と同じくらい（10年の人口: 旗切 231 → 233、decisions 91 → 92）。self_check（1年・C++、1年・`--self-check-gdscript`、10年・`--self-check-gdscript`）は全部「結果: OK」。

### 重さ（`bench_psyche.gd -- --people 2000 --days 200 --on`、`GODOT_EXCLUSIVE=1`、前と後を続けて回した。ms/日）
| | 心の層（前→後） | 1日（前→後） |
|---|---|---|
| C++ | 37.56 → 37.77（+0.6%） | 325.2 → 333.1（+2.4%） |
| `--gdscript`（置き換えただけ） | 123.1 → 442.0（+259%） | 423.4 → 764.8（+81%） |
| `--gdscript`（直し1: 割引 β δ^t と週の残りの値を覚える） | 123.1 → 240.9（+96%） | 423.4 → 537.9（+27%） |
| `--gdscript`（直し2: 村を出る決めの「ここ」の見込みを行き先の間で使い回す） | 123.1 → 156.8（+27%） | 423.4 → 462.4（+9%） |

- C++ は線（+10%）の中。`--gdscript` は1日は線の中、心の層は線の外（+27%）。直しは2回で止めた（作業者の決まり）。
- 元: GDScript の決定の数学は組み込みの約10倍重い（1回あたり exp 0.99µs・log 1.45µs・pow 2〜2.5µs、組み込みは 0.09µs）。GDScript の1つの演算と関数を呼ぶ重さそのもの。
- 直し1・2は、同じ値を何度も数える所を覚えておくだけ（C++ の双子は毎回数える。parity・DIGEST が変わらないことで確かめた）。
- 残りの重さ（60日の数え）: 暮らしの組の月ごとの満ち（`plan_path` の exp 4つ × 12か月 × 組の数）、村を出る決めの行き先ごとの結婚の見込み、才の帳面の log、`randfn`（talent の観察）。

### 試験（土台 1bd5991 からの変更の後）
- `tools/run_tests.sh --tier full -j3`（90本）: 通らなかったのは3本。`test_eco_hooks`（決まった指紋の文字列。値が 1e-9 ほどずれた。取り直して PASS 45/45）、`test_org_forms`（known_failures の KNOWN のまま）、`world/pixel/test_determinism.gd`（混んだ箱で 600 秒の時間切れ。単独で回して 11/11 合格、576 秒で上限の 600 秒に近い）。ほかの 87 本は合格。
- `sim/api/test_det_math.gd`（新しい。smoke に入れた）28/28、`native/test_native_parity.gd` 68/68。
- DIGEST 3本（`tools/test/digests.sh`）ok、SOA_MISMATCH 0。

## ほかに OS（や機械）で答えが変わり得る物（見つけた所と直し方の案。この作業では直していない）
| 物 | 場所 | 変わり得るわけ | 直し方の案 |
|---|---|---|---|
| StringName の並べ替え | `Array.sort()` で辞書の鍵を並べる所（`*.keys().sort()` が約 40 か所。全部は見ていない。見た所 `sim/nation/nation_industry.gd:281`（int）・`world_nation_geography.gd:155`（String）は安全） | StringName の大小は中の文字列の番地の順（作られた順・起動のしかた・OS で変わる。WINDOWS_EXPORT 9章） | 名前の鍵は `NameSort.sort`。見落としを捕まえる試験: 起動の始めに名前をいくつか逆の順で作ってから回し、DIGEST が同じかを見る |
| 時間で区切る1日 | `EconomySim.step(budget_usec)`・`NationStatusStepper.step(budget_usec)` | 窓ありの遊びでは1フレームの予算（実時間）で日の途中で止まる。止まる所が機械の速さで変わり、その間にほかの層が読み書きすると答えが変わり得る（headless の probe・self_check は1日を一気に進めるので出ない） | 予算 1µs と無限で同じ DIGEST になるかの試験を足す。変わるなら、区切りの途中では他の層が読まない形にする |
| `hash()` を乱数の種に | `sim/nation/nation_status.gd:531・2057`、`world_nation_geography.gd:102・220`、`nation_seeder.gd:9`、`nation_status_stepper.gd:1438` ほか | Godot の中の murmur3 なので OS では変わらない。ただし Godot の版を上げると変わり得る | 種は `HouseholdLayer.mix_int` のような自前の混ぜに寄せる（版を上げる前に） |
| 数を文字にする | `"%.9f" % x`（`test_eco_hooks` の指紋など）、`str(float)` | Godot の文字の作り方（版による）。sim の答えには入っていない（DIGEST は `var_to_bytes`） | sim の決めに文字にした数を使わない（今は使っていない） |
| 平らな世界 | `world/flat/flat_geography.gd`（pow・exp・cos）、`seasonal_region_routes.gd`（cos） | OS の数学の庫 | 平らな世界を sim の答えに使う時に `DetMath` へ |
| 地球の世界の地理と気候 | `world/planet/`（geo・earth_regions・earth_climate・earth_population・earth_agri の sin・cos・atan2・asin・exp・pow・log）、`world/geography/local_surface.gd` | OS の数学の庫。国の模型と地球の世界の地域の雨・広さ・距離に入り得る（流れ者の DIGEST の道には入らない） | 地球の世界を DIGEST で比べる前に `DetMath` へ（asin は DetMath に足す） |
| 画面だけの所 | `player_ui`・`crowd_view`・`pixel_village`・`night_view`・`stations_view`・`village_dev` の sin・cos | 絵だけ（sim に入らない） | そのまま |
| 文字を数にする | `String.to_float`・JSON の数・GDScript の10進の字 | Godot 自前の読み（OS の庫ではない）なので OS では変わらない見込み | 係数はビットで持つ（DetMath と同じ）。データの数は今のまま |
