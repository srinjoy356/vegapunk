# Vegapunk results

_Generated 2026-11-06 01:00 UTC from `cache/`._

## Edison on the hackathon PRs

198 of 233 competing PRs through the sandbox so far.

| Verdict | PRs |
|---|---|
| Proven | 160 |
| No tests | 19 |
| Broken | 13 |
| Unreproducible | 6 |

76 of them also change TypeScript tests, which Edison lists but does not run yet.

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

59 contested issues ranked; 39 with satellite verdicts.

- #768 Add DeepSeek Harness as an agent provider: #1104 (0.47), #1344 (0.45); pick #1104, confidence low; shaka picked #1344, combined pick is #1104; lilith picked #1344, combined pick is #1104
- #769 Add email as a messaging platform: #1211 (0.49), #1241 (0.48), #1213 (0.40), #1240 (0.30); pick #1211, confidence low; lilith picked #1240, combined pick is #1211; shaka picked #1241, combined pick is #1211
- #770 Enable the Linear connector: #1416 (0.88), #1428 (0.75), #1468 (0.71), #1118 (0.65); pick #1416, confidence medium
- #771 Scheduled messages to agents in a room: #1153 (0.76), #1154 (0.42); pick #1153, confidence high
- #774 Add Mistral Vibe as an agent provider: #1059 (0.82), #1199 (0.38); pick #1059, confidence high
- #781 Add Amp as an agent provider: #1470 (0.51), #1201 (0.36); pick #1470, confidence high
- #783 Add Factory Droid as an agent provider: #1151 (0.53), #1195 (0.49); pick #1151, confidence low
- #784 Add Cline CLI as an agent provider: #1137 (0.82), #1142 (0.65), #1121 (0.39); pick #1137, confidence high
- #790 Add Google Chat as a messaging platform: #1337 (0.86), #1278 (0.41); pick #1337, confidence high
- #791 Add Zulip as a messaging platform: #1451 (0.87), #1279 (0.42); pick #1451, confidence high
- #792 Add Signal as a messaging platform: #1228 (0.78), #1041 (0.34); pick #1228, confidence high
- #794 Add Rocket.Chat as a messaging platform: #1242 (0.91), #1280 (0.35); pick #1242, confidence high
- #796 Add SMS (Twilio) as a messaging platform: #1244 (0.76), #1233 (0.50), #1049 (0.42); pick #1244, confidence high
- #799 Bring-your-own messaging app (generic webhook platform): #1461 (0.90), #1216 (0.61), #1453 (0.50); pick #1461, confidence high
- #800 Cancel a pending message before the agent picks it up: #1403 (0.87), #1437 (0.83), #1496 (0.70), #1405 (0.59), #1164 (0.37); pick #1403, confidence low; lilith picked #1437, combined pick is #1403
- #801 Deliver messages sent mid-turn to the running agent (steering): #1494 (0.81), #1499 (0.76), #1465 (0.64), #1445 (0.58), #1055 (0.35); pick #1494, confidence medium
- #803 Show tool input and output in the channel, safely: #1387 (0.58), #1414 (0.52), #1215 (0.31); pick #1387, confidence medium; lilith picked #1414, combined pick is #1387
- #804 Handle edits to a message the agent hasn't picked up yet: #1502 (0.87), #1503 (0.73), #1473 (0.57), #1329 (0.51), #1046 (0.30); pick #1502, confidence medium
- #805 Room invites should respect who can talk to an agent: #1043 (0.89), #1449 (0.65), #1406 (0.56), #1443 (0.28), #1287 (0.23), #1549 (0.00); pick #1043, confidence high
- #806 Prettify the agent controller CLI output: #1042 (0.66), #1402 (0.56), #1450 (0.54), #1038 (0.46), #1442 (0.42), #1186 (0.22), #1408 (0.20), #1486 (0.06); pick #1042, confidence medium; lilith picked #1402, combined pick is #1042
- #816 Add the GitLab connector: #1424 (0.85), #1495 (0.84), #1423 (0.79), #1144 (0.74), #1491 (0.39), #1410 (0.37), #1051 (0.23); pick #1424, confidence low; shaka picked #1495, combined pick is #1424; lilith picked #1495, combined pick is #1424
- #818 Add the Bitbucket connector: #1456 (0.81), #1205 (0.74), #1009 (0.07); pick #1456, confidence medium
- #819 Add the Notion connector: #1401 (0.86), #1341 (0.75), #1116 (0.35), #1054 (0.23); pick #1401, confidence medium
- #821 Add the Asana connector: #1053 (0.53), #1455 (0.43), #1444 (0.39); pick #1053, confidence medium
- #823 Add the New Relic connector: #1435 (0.51), #1052 (0.45), #1396 (0.39), #1145 (0.38), #1206 (0.31), #1389 (0.18), #1457 (0.09); pick #1435, confidence medium; shaka picked #1052, combined pick is #1435
- #825 Add the PagerDuty connector: #1060 (0.88), #1398 (0.53), #1391 (0.47), #1432 (0.12); pick #1060, confidence high
- #826 Add the Grafana connector: #1394 (0.91), #1314 (0.28); pick #1394, confidence high
- #827 Add the Supabase connector: #1084 (0.85), #1467 (0.43), #1409 (0.42), #1209 (0.41), #1343 (0.36); pick #1084, confidence high
- #828 Add the Cloudflare connector: #1475 (0.75), #1076 (0.59), #1400 (0.45), #1393 (0.41), #1208 (0.39), #1462 (-0.07); pick #1475, confidence high
- #830 Add the HubSpot connector: #1306 (0.30), #1294 (0.18); pick #1306, confidence medium
- #831 Add the Azure DevOps connector: #1351 (0.71), #1282 (0.41), #1304 (0.41); pick #1351, confidence high
- #832 Add the Box connector: #1390 (0.88), #1207 (0.41); pick #1390, confidence high
- #835 Add the Monday.com connector: #1136 (0.83), #1218 (0.47), #1458 (0.11); pick #1136, confidence high
- #837 Add the Trello connector: #1509 (0.75), #1134 (0.66), #1126 (0.56), #1217 (0.21); pick #1509, confidence medium; lilith picked #1134, combined pick is #1509; shaka picked #1134, combined pick is #1509
- #838 Add the Airtable connector: #873 (0.79), #1264 (-0.14); pick #873, confidence high
- #840 Add the Snowflake connector: #1427 (0.79), #1364 (0.56), #1212 (0.01); pick #1427, confidence high
- #841 Add the BigQuery connector: #1425 (0.78), #1266 (0.33), #1347 (0.19); pick #1425, confidence high
- #842 Add the Intercom connector: #1141 (0.81), #1464 (0.42), #1489 (0.36); pick #1141, confidence high
- #843 Add the Zendesk connector: #1388 (0.96), #1204 (0.30); pick #1388, confidence high

## Sealed predictions

None yet.

## Cost

Paid model spend: $0.0166 of the $1.00 cap (50 gpt-4o-mini calls). Claude (Shaka) and Gemini (Lilith) run on existing subscriptions.
