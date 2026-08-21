# Chart Ideas for VR Dashboard
*Research-based, 2026-03-17*

## What the best Ukrainian Rada analytics do (VoxUkraine, Texty, CHESNO, Rada4You)

Key insight: **raw vote counts per faction are nearly useless for analysis.**
What actually matters:
- **Participation rate** — were deputies present and did they vote?
- **Voting direction** — what % of a faction's votes were "Za"?
- **Faction discipline** — do members vote as a bloc or split?
- **Coalition dependency** — does the ruling party need other factions to pass bills?
- **Cross-time trends** — how did behavior change across sessions?

---

## Tier 1 — Implemented with compact daily faction aggregates

### 1. ✅ IMPLEMENTED — Active-participation heatmap and silent-presence gap
The session heatmap uses active votes (`за + проти + утримались`) over all member-vote
opportunities. Formal presence is shown separately as a sorted dumbbell against active
participation, so the gap directly measures `не голосував` instead of hiding it behind a toggle.

### 2. ✅ IMPLEMENTED — Faction "За" rate trend lines
Top 5 factions by vote volume, 3-session rolling average, consistent color map across charts.

### 3. ✅ IMPLEMENTED (modified) — Pass rate bar chart
Changed from "quorum margin" to "% bills passed per session" — more intuitive, uses per-bill data. Color-coded: green ≥70%, yellow 40-70%, red <40%.

### 4. ✅ REPLACED 2026-08-20 — Normalised partner dependence
The stacked area was removed because raw contributions mostly measured faction size. The new
view separates successful law-stage votes where Слуга народу had its own 226 from those requiring
partners, then ranks partners by `За / all member-vote opportunities`; strict necessity remains
an exact tooltip count.

---

## Tier 2 — Needs new Python pre-processing of plenary_vote_results-skl9.tsv

### 5. Top absentees table
**What**: Ranked list of deputies by absence rate (sorted worst first) for selected date range. Columns: photo, name, faction, % absent, # sessions missed.
**Why useful**: Accountability — who skips work? Reference: CHESNO, Texty attendance analysis.
**Data needed**: Pre-process TSV → `deputy_attendance.json` { deputy_id: { present, absent, total, faction_id } }
**Script**: `build_deputy_attendance.py`

### 6. ✅ IMPLEMENTED 2026-08-20 — Mobilisation × faction discipline
Each faction is positioned by active participation and agreement with its unique modal active
choice. Absent and non-voting members affect mobilisation but not discipline; ties and cases with
fewer than two active members are excluded explicitly. The two-dimensional view distinguishes
an attendance problem from an internal split.

### 7. Deputy vote scatter (simplified UMAP)
**What**: 2D scatter — each point = 1 deputy, positioned by voting similarity (PCA/UMAP of vote vectors). Color by faction. Interactive tooltips.
**Why useful**: Shows the "real" parliamentary map — which deputies from different factions vote alike.
**Data needed**: Full TSV → vote matrix → PCA → 2D coordinates JSON.
**Script**: `build_deputy_embedding.py` (needs scikit-learn).
**Reference**: Texty "Три етапи Ради" — most iconic Ukrainian Rada visualization.

### 8. Faction pairwise similarity matrix
**What**: N×N grid of faction pairs, color = % sessions where both factions voted the same way.
**Why useful**: Shows hidden cross-faction alliances and opposition groupings.
**Data needed**: Pre-process TSV → `faction_similarity.json`
**Reference**: Rada4You publishes this monthly.

---

## Tier 3 — Advanced / research-grade

### 9. Deputy voting network graph
**What**: Force-directed graph — nodes = deputies, edges = drawn when two deputies vote together on > 70% of bills. Clusters = real coalitions.
**Why useful**: Reveals the actual power structure vs. formal faction declarations.
**Data needed**: Full deputy × bill matrix + D3.js or Sigma.js for rendering.
**Reference**: VoxUkraine "Мерехтлива Рада", Rubryka deputy network.

### 10. Reform support score (ККД-style)
**What**: Individual deputy score based on voting for a curated list of "important" bills. Ranked list.
**Why useful**: Accountability metric, reproducible KPI for each deputy.
**Data needed**: Expert-curated bill list + full vote matrix.
**Reference**: VoxUkraine ккд.voxukraine.org

---

## Tier 2 — ідеї з фідбеку (потребують нової Python-обробки)

### 11. % «За» залежно від суб'єкта законодавчої ініціативи
**Що**: Порівняння рівня підтримки законопроектів залежно від того, хто їх вніс — Президент / КМУ / депутати.
Два рівні:
1. Загальний % «За» по кожному суб'єкту (bar chart або grouped bars).
2. Розбивка по фракціях: для кожного суб'єкта — яка фракція як голосувала (heatmap або grouped bars).
**Чому корисно**: Показує, чи фракція підтримує ініціативи влади vs опозиційних депутатів — реальний індикатор лояльності.
**Дані**: З TSV потрібно витягти ініціатора по кожному законопроекту (є в даних? треба перевірити). Якщо є — `build_bill_initiator.py`.
**Тип графіку**: Grouped bar або faceted bar.

### 12. Аналіз голосувань «Проти»
**Що**: Окремий блок по голосам «Проти» — відсоток «проти» по фракціях у часі, або які законопроекти зібрали найбільше «проти».
**Чому корисно**: Голосів «проти» зазвичай небагато — це сильний сигнал щодо реальної позиції фракцій. Виявляє системну опозицію vs разові протести.
**Дані**: Ті самі TSV-дані, просто фільтр за vote = "Проти".
**Тип графіку**: Trend line (% проти по фракціях) + можливо таблиця найбільш «протестних» законопроектів.
**Пріоритет**: Відносно простий — дані вже є, потрібна лише нова агрегація.

---

## Tier 3 — Advanced / research-grade (продовження)

### 13. Хітмап: голосування фракцій по депутатських законопроектах vs фракція авторів
**Що**: По законопроектах від депутатів (не Президент/КМУ): рядки = фракція авторів, стовпці = фракції, колір = % «За» відповідної фракції.
**Чому корисно**: Показує міжфракційну кооперацію та лояльність. Чи підтримують «слуги» законопроекти від опозиції, і навпаки.
**Дані**: Потребує визначення авторів законопроектів + їхньої фракційної приналежності. Складний join.
**Тип графіку**: Heatmap N×N (фракція авторів × фракція голосуючих).
**Складність**: Висока — нетривіальний data pipeline.

---

## UX: кольори фракцій за офіційною айдентикою

**Ідея**: Замість поточної довільної палітри — використовувати офіційні партійні кольори фракцій (Слуга народу — зелений, ОПЗЖ — синій, Батьківщина — червоний і т.д.).
**Чому**: Більш інтуїтивне зчитування для аудиторії, яка знає партії.
**Де застосувати**: Всі фракційні графіки — тренд підтримки, мобілізація × дисципліна, dumbbell, heatmap і партнерський dot plot.
**Реалізація**: Захардкодити color map в `factionColors` об'єкті, замінити поточну `COLORS` палітру.
**Пріоритет**: Low-effort, high-impact — швидке UX-покращення.

---

## What to replace / remove from current dashboard

| Current chart | Problem | Replace with |
|---|---|---|
| Faction stacked bar (raw counts) | ✅ REMOVED — replaced by normalised faction diagnostics and partner support | Done |
| Attendance bar (by date, single metric) | ✅ REMOVED — replaced by the active-participation heatmap and presence→activity dumbbell | Done |
| Donut (passed/failed) | ✅ REMOVED — compact totals remain in the collapsed output section | Done |

---

## Implementation status

✅ **Done:**
1. Tier 1 #2 — Faction "За" rate trend lines (top 5, rolling avg)
2. Tier 1 #3 — Pass rate bar chart (modified from quorum margin)
3. Tier 1 #4 — Normalised partner dependence
4. Tier 1 #1 — Active-participation heatmap and silent-presence gap
5. Tier 2 #6 — Mobilisation × faction discipline

**Next priority:**
6. **Tier 2 #5** — Deputy absentee table (needs new Python script ~1hr)
7. **Tier 2 #7** — Deputy scatter plot (needs scikit-learn, most complex)

---

## UX improvement: зум-навігація для трендових графіків

**Стосується:** C1 (% голосів «за» по фракціях) та C3 (внесок фракцій у голоси «за»)

**Ідея:** Ці два графіки мають показувати **завжди весь діапазон дат** (не залежати від фільтра дат у хедері). Замість цього — під основним графіком маленький «overview» графік (brush/range selector), який дозволяє зумити на потрібний проміжок.

**Як працює:**
- Основний графік показує обраний діапазон (зумлений)
- Під ним — мініатюрний графік з повними даними + виділена область (drag handles)
- Користувач тягне рамку на мініатюрі → основний графік оновлюється
- За замовчуванням показується останні 3 місяці, але видно повну картину

**Реалізація:**
- Chart.js не має вбудованого brush — варіанти:
  1. `chartjs-plugin-zoom` (pinch/scroll zoom + pan) — найпростіше, але без мініатюри
  2. Два Chart.js інстанси: основний + маленький overview, синхронізовані вручну через `onPan`/`onZoom` callbacks
  3. Перейти на D3.js для цих двох графіків (D3 має native brush) — більший scope
- Рекомендовано: варіант 2 (два Canvas) — повний контроль, без нових залежностей окрім zoom plugin

**Пріоритет:** Medium (після C4 heatmap)

---

## Джерела натхнення

### VoxUkraine: "Несамодостатня монобільшість: хто голосує, а хто прогулює засідання парламенту"
https://voxukraine.org/nesamodostatnya-monobilshist-hto-golosuye-a-hto-progulyuye-zasidannya-parlamentu

Ключові ідеї для запозичення:
- **Line chart тренду відвідуваності** по сесіях (падіння з 87% до 76%)
- **Scatter plot** — розкид відвідуваності по фракціях (показує дисципліну)
- **Таблиці-рейтинги** — топ найприсутніших та найбільших прогульників
- Окремий аналіз "фінальних" голосувань (закони "в цілому") vs всі голосування
- Порівняння "присутність" (картка вставлена) vs "участь у голосуванні" (кнопка натиснута)
- Виключення депутатів на військовій службі / у декреті зі статистики
- Кореляція підтримки реформ vs загальна відвідуваність

### VoxUkraine: "Зміни в моно: що сталося зі Слугою народу за 5 років депутатства?"
https://voxukraine.org/zminy-v-mono-shho-stalosya-zi-slugoyu-narodu-za-5-rokiv-deputatstva

Ключові ідеї для запозичення:
- **UMAP scatter plots по сесіях** — кожна точка = депутат, близькість = схожість голосування, колір = фракція. Показує фрагментацію монобільшості у часі (→ пов'язано з нашим #7)
- **Система скорингу** голосів: +1 за реформу, −1 проти, 0 утримання/відсутність — створює "реформний індекс" (→ пов'язано з #10)
- Кількість "активних" депутатів по сесіях (зниження з 263 до 95)
- "Мовчазна присутність" — депутати зареєстровані, але не голосують (важлива метрика)
- Відстеження зміни фракційної згуртованості: від монолітного блоку до фрагментованих груп
- Виявлення де-факто коаліцій (не формальних, а за фактичним голосуванням)

---

## Data architecture note

Tier 1 health charts read the compact pre-built `faction_diagnostics.json`; they never parse the
68 MB source TSV in the browser. Tier 2/3 additions likewise require Python-generated summaries.
Tier 3 requires D3/Sigma for graph rendering — much larger scope.

The TSV source file (`plenary_vote_results-skl9.tsv`, 68MB) should **never** be fetched in browser.
All heavy processing stays in Python pre-build scripts.
