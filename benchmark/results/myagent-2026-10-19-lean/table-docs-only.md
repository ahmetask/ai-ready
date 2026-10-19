Medians per task over repeated runs; tokens include cache reads and writes.

| task | tokens before | tokens after | change | cost $ before | cost $ after | change | turns before | turns after | change | seconds before | seconds after | change | passed before | passed after |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| add-agent | 50,968 | 17,604 | -65% | 0.049 | 0.026 | -48% | 8 | 3 | -62% | 23 | 14 | -40% | 3/3 | 3/3 |
| auth | 24,550 | 28,784 | +17% | 0.023 | 0.032 | +36% | 3 | 3 | +0% | 14 | 12 | -15% | 3/3 | 3/3 |
| commands | 30,131 | 7,827 | -74% | 0.041 | 0.010 | -76% | 6 | 1 | -83% | 14 | 5 | -67% | 3/3 | 3/3 |
| storage | 22,917 | 20,028 | -13% | 0.018 | 0.031 | +75% | 3 | 3 | +0% | 13 | 11 | -16% | 3/3 | 3/3 |
| todo-count | 45,638 | 49,567 | +9% | 0.055 | 0.060 | +9% | 8 | 9 | +12% | 18 | 18 | +3% | 3/3 | 3/3 |
| **all (sum of medians)** | **174,204** | **123,810** | **-29%** | **0.187** | **0.158** | **-15%** | **28** | **19** | **-32%** | **82** | **60** | **-27%** | 15/15 | 15/15 |
