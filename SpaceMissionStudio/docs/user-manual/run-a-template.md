# Run a template

How to run one of the 27 ready-made missions and look at what it did.

## In the app

1. Start the app: `spacemissionstudio gui` (or from your application
   menu if you used an installer). It opens on **Templates**, in the scenario tree.
2. Click a template, for example **22 - Starter: your first LEO
   satellite**. Its description appears below the list: what it shows
   and what to look at.
3. Click **Open Template**. The **Scenario Editor** tab shows the
   mission; **Explain**, in the side panel on the right, summarises it.
4. **Run** on the toolbar, or `Ctrl+R` (the mode beside it says
   **Single run**). A strip under the top bar shows what the run is
   doing, how far it is and the time left; **Cancel** (`Esc`) stops it.
   Template 22 takes a few seconds.
5. The **Results** tab opens. Pick a quantity in **Series**, for example
   `my-sat.position_N`, or click one of the **Suggested** buttons.
6. Open the **Events** tab to see ground-station passes and eclipses.

To keep a copy you can change, use **File > Save As...** first. The
template file itself is never changed.

## From the command line

```bash
cd SpaceMissionStudio
spacemissionstudio run spacemissionstudio/scenarios/templates/22_starter_first_leo_satellite.json --out-dir out
```

You should see `Wrote 20 result file(s) to out:` followed by the files.
`out/` then has one CSV file per quantity, `events.csv` and
`provenance.json`.

## Which template?

The [template catalog](../../spacemissionstudio/scenarios/templates/README.md)
lists all 27 with what each one teaches and a suggested order. Start with
01 (the simplest orbit), then 22.

**More detail:** User Manual section 4,
[Your first simulation](../../USER_MANUAL.md#4-your-first-simulation-in-five-minutes).

---

**Next:** [Customize a template](customize-a-template.md) ·
[Read the results](read-the-results.md)
