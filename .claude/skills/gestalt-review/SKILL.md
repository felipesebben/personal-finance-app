---
name: gestalt-review
description: Review a Home Finances page or a frontend change against Gestalt principles (proximity, common region, similarity, focal point, figure-ground, continuity, symmetry, closure, common fate, Prägnanz), pre-attentive attributes and cognitive load, plus this app's own layout rules, and report concrete fixes. Use when building or changing anything in frontend/ (pages, sections, ui.py, charts), before handing UI work over for Felipe's check, or when asked to review the frontend's layout.
---

# Gestalt review

People don't read a page element by element: they see groups first, then what's in them. A page whose groups match its questions is understood at a glance; one where everything sits on the same background, at the same distance, in the same weight reads as a wall. This review checks that the grouping the eye makes is the grouping we meant, and that nothing on the page costs attention without paying it back.

The app is organised around questions (see CLAUDE.md, "Product intent"): each tab answers one, and each card inside it answers a smaller one. The review is about whether the layout says so.

## The reference

Felipe's reference is a design-driven dataviz course, `notes/references/Learn_Design_Driven_Data_Visualization.pdf`. It sits in the gitignored `notes/` folder on purpose: its licence (CC BY-NC-ND) forbids redistributing or adapting it, so never commit it, copy it into the repo, or quote it at length. Read it locally when it's there (most of it is in its slides' pictures, so render pages to look at them; text extraction misses most of it). The rules below are the general principles it teaches, restated for this codebase. Where the two disagree, ask Felipe.

## Procedure

1. **Pick the scope.** A whole page (`frontend/pages/*.py` and the `frontend/sections/*` it renders), or only what a diff touches plus its neighbours: a change can break the grouping of what's around it.
2. **Inventory the page top to bottom.** For each tab, list every visible block in order: filter rows, cards, charts, tables, captions, expanders. Note which ones sit inside a `ui.card`, and their widths (`st.columns` ratios) and heights.
3. **Write each block's question** in one line ("How is the month building up?"). A block with no question is decoration or noise. Two blocks with the same question should be one block, or be clearly one group. Check the order: from the most aggregated answer to the most detailed (see Continuity).
4. **Check the principles below**, in order. Each finding names the principle, the place (`file:line`), what the eye does now, and the fix in this codebase's own idioms.
5. **Render and look.** Charts: render the Altair spec to PNG (vl-convert in a scratch venv) on a white background, as the card shows it, and look at it. Pages: drive them with AppTest against the running app, and say plainly what you couldn't see (AppTest has no pixels; Felipe's laptop and phone are the final check).
6. **Report** as plain text (Felipe's terminal garbles tables and headings): the findings most-harmful first, each with its fix, then what you checked and found fine in one line. Don't fix anything unasked; offer to.

## The Gestalt principles, as they apply here

**Proximity.** Things that belong together sit closer to each other than to anything else. Inside a card the gap is small (`gap=None` or "small"); between cards it's bigger (`gap="medium"` on the columns). A caption belongs to the chart it explains, directly under its title, never floating between two cards. A filter sits directly above what it filters, as close to its target as the layout allows.

**Common region.** One question, one card. Every chart and every KPI lives in a `ui.card(...)` (a bordered container with key `hf-card-…`, which ui.py's CSS rounds and lifts with a soft shadow) with its question as the `st.subheader`. Nothing analytical sits loose on the page background. Don't nest cards inside cards; use columns inside one card instead. The card is the only container: a chart inside it has no background, frame or box of its own (`analytics_charts.finish` sets `background="transparent"`; sparklines too), so the region reads as one surface.

**Similarity.** Things that do the same job look the same. KPIs all go through `ui.kpi` (label above, number, ▲/▼ lines), never a mix of `st.metric` and custom HTML in one row. Cards in one row have the same height (`ui.card(key, height=...)`), and every card has a chart slot at the same height (`charts.SPARK_HEIGHT`); a card with nothing to draw yet holds the slot with `ui.empty_chart(...)`. Icons come from one family (Streamlit's `:material/…:`), never mixed with emoji. Colours keep their one job (ui.py docstring): brand green = this month / the household / what's picked / actions, grey = what it's compared with, orange ▲ = more, blue ▼ = less. A colour that means something on one chart can't mean something else on the next.

**Focal point and figure-ground.** Each view has exactly one hero: the answer, biggest (3rem via `ui.kpi(hero=True)`), top left, where the eye lands first. Everything else is visibly secondary. In a chart, one thing is highlighted (brand green) and the rest stays grey, so the eye goes to the point being made; colour that highlights everything highlights nothing. Data is the loudest ink: axes, grid and labels stay quiet (`analytics_charts.finish`), never absent, so a chart sits on its axis line instead of floating. Cards are the figure, the page background the ground: white cards on the theme's off-white.

**Continuity.** Reading follows a Z across visual pages (an F across dense text): top left, across, down, across. Put the questions in that order, from the most aggregated to the most detailed: the answer, then over time, then by category, then why it differs, then single days. Axis titles sit at the end of their axis, where reading finishes: x at the bottom right (`x_title`), y at the top (`y_title`).

**Symmetry and alignment.** Edges line up: cards in a grid share left and top edges, and a hero beside a 2 x 2 grid is exactly two cards plus the gap tall. Side-by-side halves of a card (a chart and its breakdown) split evenly unless one clearly leads. Misaligned edges read as separate groups even when they aren't.

**Closure.** Implied shapes are fine and reduce ink: a calendar needs no grid lines between days, rounded cells close it; a sparkline needs a baseline, not a box. Don't draw borders around marks.

**Common fate.** Things that change together are grouped. One filter row drives everything below it, so it sits above all of it, and every block below it obeys it (including drill-down tables and expense lists). If one block ignores a filter, it can't sit under that row without saying so. A tap that picks something (a clickable bar) changes what sits beside it, in the same card, never somewhere further down.

**Prägnanz (simplicity).** Prefer the simplest arrangement that keeps the groups clear: fewer, larger groups over many small ones; one legend shared by two calendars over two legends; a question as the title over a title plus a "what this shows" line. No effects, 3D, gradients on marks or fancy containers.

## Pre-attentive attributes: what the eye sees before reading

The eye notices position, length, size, colour intensity and hue before attention starts. Use them for what they're good at:

- **Quantities**: position and length first (bars from a zero baseline, lines on a shared scale), then colour intensity (heatmaps, the calendar). Never hue for magnitude, never area or angle when a bar would do.
- **Categories**: hue and position. More than a handful of hues stops being pre-attentive: fold the rest into grey or "Other", or facet.
- **Emphasis**: one attribute at a time, on one thing. Don't encode the same value twice (a bar's height and a colour ramp on the same bars): the reader starts asking about the design instead of the data.
- **Shades**: three to five distinct levels on a view, the text colours included (ink, muted, the accent, grey, one data colour). The calendar's ramp is one hue, light to dark.

## Cognitive load

Some of a page's difficulty is the question itself; the rest is what the design adds. Remove the added part, and spend a little on explanation where it saves a lot of puzzling:

- **Data-ink.** Every pixel either shows data or helps read it. No chart backgrounds, frames, heavy grids, decorative icons or flags; one quiet axis line.
- **Text hierarchy.** Page title, then card question (subheader), then one explanatory caption, then the fine print, each visibly smaller and quieter. Sentence case, Roboto throughout, no all-caps, no italics for whole sentences, bold only for the answer.
- **Context for every number.** A bare figure says little: give it the comparison (▲/▼ against last month and the usual month) and, when there's room, its trend (a sparkline). That's the shape of every `ui.kpi` card.
- **Choice overload.** Few controls, each with a sensible default, so the page answers before anyone touches it. A clickable chart opens on its biggest bar; a filter row opens on "Everything".
- **Whitespace over borders.** Segment with space; the card is the one border allowed. Give charts height rather than squeezing them; scrolling is fine, cramming isn't. Still, the most important answer must fit on the first screen, because attention drops quickly as people scroll.
- **Honesty.** Bars start at zero; a truncated axis needs a stated reason. Show partial months as partial ("so far", "to date") and never project them. Compare like with like (the same days of each month).
- **Design for mistakes.** People log wrong amounts and categories; a view that makes an outlier visible should let them get to the expense behind it.

## Common findings in this codebase

- A chart or table outside any card: wrap it in `with ui.card("<key>"):` with its question as the subheader.
- A chart with a grey box on a white card: it's missing `analytics_charts.finish` (or `daily_charts._spark`), which set the background transparent; Streamlit's theme otherwise paints the page colour behind it.
- Cards in a row with different heights: give them `height=` and a fixed chart slot.
- A legend inside one of two side-by-side charts: it changes that chart's size. Use one shared legend under both (the calendars' `_calendar_legend`).
- Squeezed charts: give height; scrolling is fine, squeezing isn't.
- An ⓘ that does nothing: help must go through Streamlit's own `help=` (`ui.kpi(..., help=...)` does), not an HTML `title` attribute, which phones never show.
- Text in a data colour: labels and values use the ink tokens; colour sits on the mark beside them.
- A table where a ranked bar chart would answer faster: rank it as bars (`daily_charts.pick_bars`), keep the table in an expander for the exact figures.
- A picker (selectbox) that duplicates a chart: let the chart be the picker (`on_select="rerun"` on an unlayered chart, as `pick_bars` does) and default to its biggest bar.

## Limits

This file is about grouping, layout and attention. Colour safety and chart anatomy belong to the dataviz skill; product questions (what a page should answer) to CLAUDE.md and Felipe. Don't restyle Streamlit internals: CSS in ui.py targets only our own `hf-` classes and the `st-key-hf-…` classes our container keys produce.
