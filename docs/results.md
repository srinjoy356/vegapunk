# Vegapunk results

_Generated 2026-11-04 06:36 UTC from `cache/`._

## Edison on the hackathon PRs

49 of 149 competing PRs through the sandbox so far.

| Verdict | PRs |
|---|---|
| Proven | 48 |
| Broken | 1 |

30 of them also change TypeScript tests, which Edison lists but does not run yet.

## Backtest: does Edison's evidence predict a merge?

40 past PRs that change switch-core tests (sampled half merged, half closed unmerged).

| Edison verdict | merged | closed | merge rate |
|---|---|---|---|
| Broken | 1 | 5 | 17% |
| No tests | 1 | 0 | 100% |
| Proven | 18 | 13 | 58% |
| Unproven | 0 | 2 | 0% |

AUC (Edison + Atlas score as a merge predictor): **0.792**; 0.5 is a coin flip.
Closed PRs are not all bad (some were superseded), so this is a floor, not a ceiling.

## Planted defects

| Planted fault | caught by Edison |
|---|---|
| revert-impl | 4/4 |
| hollow | 4/4 |
| skip | 4/4 |
| secret | not Edison's job (see below) |

Secret-planted twin #91153 of #1153 in a blind tribunal: flagged high/critical by shaka, lilith; reported by lilith, shaka.

## Tribunals

19 contested issues ranked; 5 with satellite verdicts.

- #768 Add DeepSeek Harness as an agent provider: #1344 (0.56), #1104 (0.51); pick #1344, confidence medium
- #769 Add email as a messaging platform: #1241 (0.46), #1211 (0.43), #1213 (0.34), #1240 (0.17); pick #1241, confidence low; lilith picked #1240, combined pick is #1241
- #770 Enable the Linear connector: #1416 (0.85), #1428 (0.76), #1118 (0.70); pick #1416, confidence medium
- #771 Scheduled messages to agents in a room: #1153 (0.94), #1154 (0.42); pick #1153, confidence high
- #803 Show tool input and output in the channel, safely: #1387 (0.57), #1414 (0.51), #1215 (0.29); pick #1387, confidence medium; lilith picked #1414, combined pick is #1387

## Sealed predictions

None yet.

## Cost

Paid model spend: $0.0017 of the $1.00 cap (6 gpt-4o-mini calls). Claude (Shaka) and Gemini (Lilith) run on existing subscriptions.
