# Historical air-alert data for Ukraine

Research checked on 23 June 2026.

## Recommendation

Use the public [Vadimkin Ukrainian air-raid sirens dataset](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset) as the bulk source. It is MIT-licensed, published as ordinary CSV files, documented as updating daily, and requires no API key or pagination.

Two files matter:

| File | Coverage observed on 23 June 2026 | Rows | Fields | Best use |
|---|---:|---:|---|---|
| [Official English CSV](https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/official_data_en.csv) | 15 Mar 2022–23 Jun 2026 | 272,699 | `oblast`, `raion`, `hromada`, `level`, `started_at`, `finished_at`, `source` | Primary, higher-authority source and sub-oblast analysis |
| [Volunteer English CSV](https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/volunteer_data_en.csv) | 25 Feb 2022–23 Jun 2026 | 101,705 | `region`, `started_at`, `finished_at`, `naive` | Consistent oblast-level series and the 25 Feb–14 Mar 2022 gap |

Ukrainian-language versions are in the repository's [`datasets` directory](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset/tree/main/datasets).

The repository regenerates the files from two Telegram histories: the official Air Alert channel and the volunteer eTryvoga channel. A World Bank study independently used this same repository's official CSV for oblast-day alert counts and cumulative active time.

## Why the API is not the right backfill method

The [alerts.in.ua API documentation](https://devs.alerts.in.ua/) confirms:

- general limits are a soft 8–10 and hard 12 requests per minute;
- the history endpoint has a stricter limit of **2 requests per minute**;
- its only documented history period is `month_ago`.

Therefore, even with a token, the documented API cannot retrieve a complete 2022–present history. The limit is not the principal problem; the absence of a historical date-range or full-dump endpoint is.

## Download

```bash
mkdir -p data/raw

curl -L \
  https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/official_data_en.csv \
  -o data/raw/official_data_en.csv

curl -L \
  https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/volunteer_data_en.csv \
  -o data/raw/volunteer_data_en.csv
```

For reproducibility, record the Git commit hash or save a dated snapshot instead of repeatedly analyzing the moving `main` files.

## Suggested source strategy

### Highest-authority historical series

1. Use the volunteer data only from 25 February through 14 March 2022.
2. Use the official data from 15 March 2022 onward.
3. Do not concatenate their overlapping periods: that would double-count alerts.

### Consistent oblast-level series

Use the volunteer CSV for the entire period. It stays at oblast level, which makes longitudinal analysis easier, but it is a volunteer-derived source. Of 101,705 rows checked, 5,014 (4.93%) have `naive=True`: when no all-clear message was available, the pipeline imputed `finished_at = started_at + 30 minutes`. Keep that flag and run a sensitivity analysis with those rows excluded.

### Raion/hromada analysis

Use the official CSV. At the checked snapshot it contained:

- 130,053 oblast-level rows;
- 107,348 raion-level rows;
- 35,298 hromada-level rows.

The publisher warns that from December 2025 alerts are mostly reported at raion level rather than oblast level. That creates a structural break. Do not interpret a post-December-2025 increase in row count as an increase in danger without accounting for the granularity change.

## Important analysis caveats

1. **Overlapping geography:** An oblast, its raions, and its hromadas can have simultaneous records. Summing durations or rows across levels will double-count. Analyze one level at a time, or merge overlapping time intervals within a clearly defined geography.
2. **Meaning of an oblast metric:** Decide whether it means “an oblast-wide alert” or “an alert somewhere inside the oblast.” They are no longer interchangeable after the reporting-granularity change.
3. **UTC:** Both repository datasets use UTC. Convert to `Europe/Kyiv` before grouping by local day; otherwise alerts around midnight will be assigned to the wrong Ukrainian date.
4. **Alerts crossing midnight:** Split intervals at local midnight before calculating daily exposure. Assigning the entire duration to the start date biases day-level results.
5. **Open intervals and imputations:** Preserve the volunteer `naive` flag. For live or same-day snapshots, also check `finished_at` before computing duration.
6. **Permanent alerts:** The publisher says the persistent Luhansk alert beginning 4 April 2022 and the persistent Crimea alert beginning 10 December 2022 are not represented as ordinary rows. Crimea is absent from the observed region labels; Luhansk's permanent period must be handled explicitly if it belongs in the research question.
7. **Source interpretation:** “Official CSV” means records reconstructed from the official alert channel, not a formal bulk export supplied by the API operator.
8. **Unit of analysis:** A sum of region-level alerts is not the number of distinct nationwide alert episodes. State whether the unit is a local alert interval, an oblast-day, a person-hour proxy, or a union of concurrent national intervals.

## Other sources reviewed

- [Kaggle: Air-raid sirens in Ukraine](https://www.kaggle.com/datasets/cashncarry/airraid-sirens-in-ukraine): CC0 and easy to download, but its page describes only 12,000+ records and was updated about three years ago. Useful as an old snapshot or validation set, not the primary current archive.
- [Unofficial Air Raid Alert API](https://raid.fly.dev/): documents a one-call full-history dump, but it is an unofficial service with less-clear provenance, licensing, and current maintenance. Treat it as a cross-check, not the canonical dataset.
- [Kyiv Digital alert history](https://kyiv.digital/storage/air-alert/stats.html): a long official-looking city history, but it is Kyiv-only HTML rather than a clean national bulk dataset.
- [Air-alarms.in.ua](https://air-alarms.in.ua/region/kropyvnytskyi): publishes statistics and says it provides custom research extracts on request, but does not expose a public national bulk file on the reviewed page.
- [Volodymyr Agafonkin's Observable notebook](https://observablehq.com/@mourner/sirens): an influential early-2022 scraped dataset/visualization under MIT, valuable for provenance checks but not preferable to the current daily CSV archive.

## Bottom line

Start with the GitHub CSVs, not the rate-limited API. For a defensible general analysis, retain both raw files unchanged, create a cleaned derived table, and document whether the study prioritizes official provenance, consistent oblast-level measurement, or fine-grained district coverage.

## References

- [Dataset repository and MIT license](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset)
- [Dataset documentation](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset/blob/main/datasets/README.md)
- [alerts.in.ua API documentation and limits](https://devs.alerts.in.ua/)
- [World Bank report citing and using the GitHub dataset](https://documents1.worldbank.org/curated/en/099061924125589588/pdf/P177312124626806b1aa081021aad774db2.pdf)
- [Data Is Plural description of the early Telegram-derived dataset](https://themarkup.org/data-is-plural/2022/06/22/monkeypox-ukraine-air-raid-alerts-and-inclusive-crossword-names)
