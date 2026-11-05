# Vegapunk results

_Generated 2026-11-05 18:02 UTC from `cache/`._

## Edison on the hackathon PRs

194 of 198 competing PRs through the sandbox so far.

| Verdict | PRs |
|---|---|
| Proven | 161 |
| No tests | 17 |
| Broken | 10 |
| Unreproducible | 6 |

74 of them also change TypeScript tests, which Edison lists but does not run yet.

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

57 contested issues ranked; 18 with satellite verdicts.

- #768 Add DeepSeek Harness as an agent provider: #1344 (0.45), #1104 (0.45); pick #1344, confidence low
- #769 Add email as a messaging platform: #1241 (0.52), #1211 (0.43), #1213 (0.34), #1240 (0.24); pick #1241, confidence medium; lilith picked #1240, combined pick is #1241
- #770 Enable the Linear connector: #1416 (0.88), #1428 (0.75), #1468 (0.71), #1118 (0.65); pick #1416, confidence medium
- #771 Scheduled messages to agents in a room: #1153 (0.76), #1154 (0.42); pick #1153, confidence high
- #774 Add Mistral Vibe as an agent provider: #1059 (0.82), #1199 (0.38); pick #1059, confidence high
- #784 Add Cline CLI as an agent provider: #1137 (0.82), #1142 (0.65), #1121 (0.39); pick #1137, confidence high
- #796 Add SMS (Twilio) as a messaging platform: #1244 (0.76), #1233 (0.50), #1049 (0.42); pick #1244, confidence high
- #800 Cancel a pending message before the agent picks it up: #1403 (0.87), #1437 (0.83), #1496 (0.70), #1405 (0.59), #1164 (0.37); pick #1403, confidence low; lilith picked #1437, combined pick is #1403
- #801 Deliver messages sent mid-turn to the running agent (steering): #1494 (0.81), #1499 (0.76), #1465 (0.64), #1445 (0.58), #1055 (0.35); pick #1494, confidence medium
- #803 Show tool input and output in the channel, safely: #1387 (0.58), #1414 (0.52), #1215 (0.31); pick #1387, confidence medium; lilith picked #1414, combined pick is #1387
- #804 Handle edits to a message the agent hasn't picked up yet: #1502 (0.87), #1503 (0.73), #1473 (0.57), #1329 (0.51), #1046 (0.30); pick #1502, confidence medium
- #806 Prettify the agent controller CLI output: #1042 (0.66), #1402 (0.56), #1450 (0.54), #1038 (0.46), #1442 (0.42), #1186 (0.22), #1408 (0.20), #1486 (0.06); pick #1042, confidence medium; lilith picked #1402, combined pick is #1042
- #816 Add the GitLab connector: #1495 (0.88), #1424 (0.85), #1423 (0.79), #1144 (0.79), #1410 (0.41), #1491 (0.39), #1051 (0.28); pick #1495, confidence low
- #819 Add the Notion connector: #1401 (0.87), #1341 (0.75), #1116 (0.38), #1054 (0.27); pick #1401, confidence medium
- #823 Add the New Relic connector: #1435 (0.51), #1052 (0.45), #1396 (0.39), #1145 (0.38), #1206 (0.31), #1389 (0.18), #1457 (0.09); pick #1435, confidence medium; shaka picked #1052, combined pick is #1435
- #825 Add the PagerDuty connector: #1060 (0.88), #1398 (0.53), #1391 (0.47), #1432 (0.12); pick #1060, confidence high
- #828 Add the Cloudflare connector: #1475 (0.73), #1076 (0.61), #1393 (0.54), #1400 (0.48), #1208 (0.44), #1462 (-0.07); pick #1475, confidence medium
- #837 Add the Trello connector: #1134 (0.88), #1126 (0.87), #1217 (0.66); pick #1134, confidence low

## Sealed predictions

None yet.

## Cost

Paid model spend: $0.0109 of the $1.00 cap (29 gpt-4o-mini calls). Claude (Shaka) and Gemini (Lilith) run on existing subscriptions.
