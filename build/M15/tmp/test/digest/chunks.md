The baseline caption chunks (from words.json: a break at a sentence end, a clause end, a pause of 150 ms or more, the 4-word limit and the 620 px line width). Keep them, merge or split them: the words and their order never change.

0. [s2] You ship Claude  (3460 ms)
1. [s2] Code client sites.  (4140 ms)
2. [s2] Clients spot it  (5300 ms)
3. [s2] *instantly.*  (5980 ms)
4. [s3] Anthropic's skill  (6640 ms)
5. [s3] file names it:  (7320 ms)
6. [s3] rounded cards,  (8360 ms)
7. [s3] one radius,  (9400 ms)
8. [s3] *same* *grey*  (10260 ms)
9. [s3] *shadow.*  (10780 ms)
10. [s4] It's not your fault.  (11390 ms)
11. [s4] Anthropic calls it  (12350 ms)
12. [s4] *distributional*  (13490 ms)
13. [s4] *convergence.*  (14290 ms)
14. [s5] Even Anthropic's  (15130 ms)
15. [s5] terracotta on  (15910 ms)
16. [s5] cream is flagged  (16590 ms)
17. [s5] as an AI look.  (17850 ms)
18. [s6] One accented  (18860 ms)
19. [s6] headline word.  (19580 ms)
20. [s6] All caps labels.  (20540 ms)
21. [s6] Fake one,  (21560 ms)
22. [s6] two, three.  (22060 ms)
23. [s7] With it on,  (22730 ms)
24. [s7] Claude plans four  (23510 ms)
25. [s7] to six hex colors,  (24270 ms)
26. [s7] reviews, *then*  (25450 ms)
27. [s7] *codes.*  (26230 ms)
28. [s8] *Anthropic*  (26890 ms)
29. [s8] *verified.*  (27270 ms)
30. [s8] Over a million  (27910 ms)
31. [s8] installs as of  (28530 ms)
32. [s8] November.  (29590 ms)
33. [s9] Type slash plugin  (30110 ms)
34. [s9] install frontend  (31150 ms)
35. [s9] design at claude  (32170 ms)
36. [s9] plugins official.  (33170 ms)
37. [s9] *Pick* *a* *scope.*  (34110 ms)
38. [s10] Then it turns on  (34740 ms)
39. [s10] *by* *itself* when  (35320 ms)
40. [s10] you ask for  (36220 ms)
41. [s10] frontend work.  (36760 ms)

## Caption modes per scene (Motion and energy rules E3 and E4)

Word mode: one word at a time on its spoken time, the emphasis words larger in the serif italic on the accent box, every word rising a little. Group mode: 2 to 6 words fill the hero zone as kinetic typography (the pipeline lays the words out: you only choose the words and the anchor, the most important word); it needs a hero zone with no text and no graphic under it, and it is the choice where the voice says something important or the scene has no graphic to show. Whenever any other text is on screen the captions are in word mode. At most 100 characters of card, chip and code text on screen at once.

- s2 (b2, stake): importance normal; text on screen 80 characters (s2-card-1, s2-dark-chip-2); graphics in the hero zone: s2-card-1, s2-dark-chip-2; the pipeline's own choice: word mode
- s3 (b3, comparison): importance normal; text on screen 26 characters (s3-dark-chip-2, s3-window-card-1); graphics in the hero zone: s3-window-card-1; the pipeline's own choice: word mode
- s4 (b4, mechanism): importance normal; text on screen 67 characters (s4-card-1, s4-handwritten-callout-2); graphics in the hero zone: s4-card-1, s4-handwritten-callout-2; the pipeline's own choice: word mode
- s5 (b5, comparison): importance normal; text on screen 47 characters (s5-light-chip-1, s5-strike-through-2); graphics in the hero zone: s5-light-chip-1, s5-strike-through-2; the pipeline's own choice: word mode
- s6 (b6, number): importance number; text on screen 0 characters; graphics in the hero zone: s6-pop-1; the pipeline's own choice: group mode
- s7 (b7, mechanism): importance normal; text on screen 51 characters (s7-check-badge-1); graphics in the hero zone: s7-check-badge-1; the pipeline's own choice: word mode
- s8 (b8, proof): importance key-claim; text on screen 34 characters (s8-stat-number-2, s8-window-card-1); graphics in the hero zone: s8-window-card-1; the pipeline's own choice: word mode
- s9 (b9, step): importance normal; text on screen 95 characters (s9-terminal-card-1); graphics in the hero zone: s9-terminal-card-1; the pipeline's own choice: word mode
- s10 (b10, payoff): importance payoff; text on screen 0 characters; graphics in the hero zone: s10-check-badge-1; the pipeline's own choice: group mode
