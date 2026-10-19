Medians per task over repeated runs; tokens include cache reads and writes.

| task | tokens before | tokens after | change | cost $ before | cost $ after | change | turns before | turns after | change | seconds before | seconds after | change | passed before | passed after |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| add-agent | 64,372 | 25,686 | -60% | 0.063 | 0.028 | -56% | 13 | 5 | -62% | 30 | 13 | -56% | 3/3 | 3/3 |
| auth | 24,940 | 18,223 | -27% | 0.030 | 0.025 | -19% | 4 | 2 | -50% | 10 | 7 | -37% | 3/3 | 3/3 |
| commands | 29,048 | 8,024 | -72% | 0.044 | 0.013 | -70% | 6 | 1 | -83% | 12 | 5 | -59% | 3/3 | 3/3 |
| storage | 21,551 | 19,833 | -8% | 0.017 | 0.032 | +85% | 3 | 4 | +33% | 9 | 10 | +17% | 3/3 | 3/3 |
| todo-count | 43,142 | 63,856 | +48% | 0.053 | 0.060 | +14% | 8 | 8 | +0% | 12 | 17 | +41% | 3/3 | 3/3 |
| **all (sum of medians)** | **183,053** | **135,622** | **-26%** | **0.207** | **0.158** | **-24%** | **34** | **20** | **-41%** | **74** | **52** | **-30%** | 15/15 | 15/15 |
