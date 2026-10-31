# Changelog — 2026-10-26

## 3.2.6 recovery baseline

- Disable experimental VideoOut admission blocking by default; retain publish-before-Reflex-sleep ordering, HDR/FG and queue observation. Explicit `BB_VIDEOOUT_BACKPRESSURE=1` remains experimental. Use `0` for the validated baseline.
- Distinguish `mode=observe only` from `mode=experimental dequeue gate` in periodic reports. A requested admission timeout/shutdown release prevents an indefinitely blocked admission; timeout recovery may exceed the target depth.
- Record the 3.2.5 scene-loading failure: GPU device loss on submit, invalid write near zero and capped SRT warnings. Both graphics and compute selection already reject failed SRT walks. The failure's root cause remains unidentified.
- Recover the complete 3.2.6 saved log: startup plus **225 telemetry periods / 18 min 46 s**, RTX 4090 / driver 621.01, HDR10 and DLSS 2×, median accepted 60 game / 120 total images per second, normal quit. All admission calls bypass blocking. No device-loss/SRT errors or failed presents occur.
- Final sampled generated / accepted-generated totals: **65,951 / 65,936**. Explicit unpresented outputs: 13. Two late no-scene/budget snapshots in the earlier pasted segment do not establish provider failure; no FSR fallback is reported.
- Keep remaining issues visible: **42,278 RT reserve-limit exclusions**, a separate RT build-budget counter, one startup stall and frame hitches up to **383 ms**. VideoOut queue window-average median: 29.45 ms; median of 37 Reflex marker averages: 54.2 ms. Rates/markers do not establish physical scanout or physical latency.

### Logging clarification

Full stdout/stderr was already saved to **`<saves folder>/last_run.log`**, rotating older runs to numbered files. The QML screen and Copy Log retain only the last **350,000 characters**. The pasted tail omitted about 6 min 50 s of telemetry; the original file retained it. Attach the saved file for future analysis. The launcher-generated exit-code footer currently exists only in the UI/clipboard, so it was matched with the saved run's Quit Game output.

### Package and local verification

| Item | Verified result |
| --- | --- |
| Source / version | `b6b9810`, `3.2.6+build102626.192649`. |
| Archive | `bloodborne_pc/dist/bbport-windows-3.2.6-recovery.zip`, 321,675,968 bytes. |
| SHA-256 | `92df4665c5a3d81b212092c14c884d3f121e537dc8a20c91a7fc3ea863d2b904`. |
| CPU regression tests | Frame admission, frame handoff, Reflex handoff, motion history, presentation telemetry and DLSS settings passed. |
| Native / package | Renderer/helpers build; CRC, matching versioned archive, native/frozen-launcher freshness and DLSS ABI 2 SR/FG passed. |
| Atlas | 20 map files, 7 art assets and frozen generator; runtime registers 16 areas. |
| Limits | GPU/physical display validation and transition/fallback matrix remain incomplete. CPU tests do not certify GPU/resource lifetimes. |

This historical documentation update left the verified ZIP unchanged. See the [October 27 update](changelog-2026-10-27.md) for the newer 3.2.7–3.2.9 work.

## 3.2.4–3.2.5 ordering and admission experiment

- End the current frame's render-submit marker, publish/notify VideoOut, then pace the next frame; copy IDs before transferring Frame ownership.
- Invalidate pending pacing IDs on swapchain recreation; keep Reflex semaphore waits outside its mutex.
- Add CPU handoff/Reflex timing and test submission order, duplicates, wait progress, timeouts, failure and recreation with mocked Vulkan.
- Add FIFO dequeue admission with real producer/consumer CPU tests and queue-depth/wait reports. Its first default-on hardware run failed; **3.2.6 supersedes that default**. A shorter marker span after moving admission is insufficient latency evidence.

## 3.2.3 capture and presentation diagnostics

- Separate parameter-slot, total vertex-capacity and character-reserve exclusions, usage peaks and largest rejected draw; leave allocation policy unchanged.
- Report provider pairs, generated/accepted totals, interval unpresented/failure counts and accepted rates every five seconds. Handle idle/counter/clock resets and use bounded writes.

## 3.2.2 HDR / FG integration

- Keep scene, HUD-less and interpolation inputs SDR. Composite the actual PC overlay before one shared final BT.709-to-BT.2020 / ST 2084 PQ conversion into a ten-bit RGB swapchain.
- Preserve plain SDR and final SDR-on-HDR desktop compensation. Synchronize scratch lifetime and support the actual overlay attachment format, including BGRA.
- Count actual accepted presentations, clear stale FG activity on skipped/failed attempts and preserve automatic fallback causes until provider change or DLSS recovery.
- Historical 3.2.2 runtime evidence observed HDR/DLSS evaluation and clean exit, but reported 467 missing RT captures and six rendering-stall messages. Current diagnostics and the later recovery run supersede its evidence gaps.
- Current 3.2.2 standalone archive: 321,578,750 bytes, SHA-256 `e00e9dbbd0c4b7dabd49ff0644ea331db0b737b92229fb5cdde6bc6f8ea4d7ff`. Older expanded documentation archives had different hashes; they are not the current standalone package.

## Next work

1. Add RT-only capture capacity with bounds, memory-cost reporting and preserved character reserve; retest the three exclusion scenes.
2. Isolate the 174–383 ms hitch windows using route/loading context and CPU/GPU timing. Avoid re-enabling command-thread blocking to reduce a marker value.
3. Expose the full saved log path/export and persist exit status; keep the live view bounded.
4. Complete HDR/window/fallback testing, other GPU generations, paper-white/peak controls and physical color/latency measurements. Reflections and local-light rendering remain unavailable.

[Feature catalog](../../features.md) · [Build](../../build.md) · [Release notes](../../Release_Notes.md) · [Launcher guide](README-LAUNCHER-V30.md).
