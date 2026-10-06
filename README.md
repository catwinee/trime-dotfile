# trime-dotfile

My [Trime](https://github.com/osfans/trime) (Rime for Android) configuration:
**26-key layout, gesture-driven, pure dark theme.**

Built and tested on an Honor 60 — Android 14, 1080×2400 @ 480dpi,
Trime 3.3.12 with librime 1.17.0.

## Gestures

| Gesture | Action |
|---|---|
| tap a letter | type it (pinyin in Chinese mode, plain ASCII in English mode) |
| **swipe up** row 1 | `1 2 3 4 5 6 7 8 9 0` |
| **swipe up** row 2 | `@ # $ % & - _ + =` |
| **swipe up** row 3 | `* ( ) ' " \| \` |
| **swipe down** a letter | that uppercase letter — committed straight away, not fed into the pinyin buffer |
| **swipe on space** | `↑` `↓` previous/next candidate (cursor up/down when nothing to pick)<br>`←` `→` move the cursor |
| **swipe up** on `⌫` | clear the whole input box |
| **swipe left** on `⌫` | drop only the current pinyin buffer |
| **swipe up** on `符号` | open the 更多 (liquid keyboard) panel |
| **swipe up** on `/` | `?` |
| long press | `a` select all · `x` cut · `c` copy · `v` paste |

The small character in a key's corner always shows what a **swipe up** will produce.

## Layout

```
q     w     e     r     t     y     u     i     o     p
·     a     s     d     f     g     h     j     k     l     ·
符号  z     x     c     v     b     n     m     ⌫
123   中英  。，   ⎵          /     ⏎
```

Four more panels: `符号` (symbols), `123` (numbers), `⌶` in the toolbar (cursor/edit),
`letter` (plain ASCII fields). The toolbar above the keyboard holds
`⋯ menu · ⌶ cursor · 📋 clipboard · 🙂 emoji · ↶ undo · ↷ redo · ⌨ hide`.

## Files

Push these four into `/sdcard/Android/data/com.osfans.trime/files/rime/`:

| File | What it configures |
|---|---|
| `trime.custom.yaml` | theme: keyboards, gestures, colours, toolbar, style |
| `default.custom.yaml` | schema list, candidates per page |
| `luna_pinyin.custom.yaml` | punctuation passthrough (so a key's corner == what it types) |
| `luna_pinyin_simp.custom.yaml` | the same, for the simplified-chars schema |

Also in this repo:

| Path | Note |
|---|---|
| `check.py` | read-only: verifies the phone's config matches this repo |
| `ref/` | stock Trime files, kept as the baseline for patch simulation |
| `AGENT_COMMENT.md` | **the long-form notes**: patch semantics, dead preset keys, why things are the way they are |
| `deploy.sh` | back up the phone's current files, then push |
| `backup/` `pic/` | gitignored — deploy snapshots and design reference screenshots |

## Deploy

```bash
./deploy.sh
```

Then on the phone: **Trime app → theme `預設` → the ↻ icon in the top bar (Deploy)**.

> The `*.custom.yaml` files take effect **at runtime** (Rime re-reads
> `<id>.custom.yaml` whenever a config is opened), so a schema *rebuild* is not
> required. Details, and why you should never hand-edit `build/`, in
> `AGENT_COMMENT.md`.

## Reading order

If you only want to use it: you're done, the table above is everything.

If you want to **change** it: read [`AGENT_COMMENT.md`](AGENT_COMMENT.md) first —
`patch:` in Trime replaces whole subtrees rather than merging, which is the
single easiest way to end up with an empty keyboard.
