---
name: dashboard-assessment
description: Assess Home Finances' analysis views as a data product — value, users, moments of use, devices, scope, data quality and business rules — by interviewing Felipe with the questions that matter for a two-person household app, then turning the answers into concrete changes. Use when planning a new view or a redesign, when asked whether the app's dashboards meet their purpose, or when Felipe asks to be interviewed about the product. Also use whenever Felipe criticises a view or asks for a change: the interview never closes, and his input is a cue for a follow-up question tied to what he has already answered.
---

# Dashboard assessment

The gestalt-review skill checks how a page is laid out; this one checks whether it should exist and for whom. It is a structured interview with Felipe, the owner and main analyst, followed by a short report mapping each answer to what it changes in the app.

## The reference

Felipe's reference is the Dataviz Clarity "Dashboard Interview Guide" spreadsheet, `notes/references/The Dashboard Interview Guide (1).xlsx`. It sits in the gitignored `notes/` folder: it is someone else's published work, so read it locally but never commit or copy it. The guide has 31 questions grouped in four steps (Define, Understand, Design, Data), written for teams building dashboards for tens to thousands of users. The questions below are the ones that matter for an app with two users, restated in this app's terms. The guide's questions on audience size, brand guidelines, data volume and column counts are left out on purpose: there are two users, the theme already exists, and the data is a few hundred rows.

## The questions worth asking here

Ask the non-obvious version: the guide's plain wording ("what is the purpose?") gets the answer CLAUDE.md already holds. Each question below comes with why it matters here and what an answer changes. Ask one at a time, never the whole list, and follow the answers.

**Define**
1. **Value.** Which decision should the app change, and has it changed one yet? It tells a decision tool, which needs targets, alerts and a "what to do" line, from a curiosity tool, which needs exploration. Name a real decision, not "save money".
2. **The question each view answers.** For every tab: what is the one question, and would you notice if the view vanished? A view nobody would miss is a candidate for removal (Prägnanz, choice overload).
3. **Scope.** What must the app never become: a budget that nags, a ledger for every cent, a way to audit each other? And what stays in Tableau? This is the line in "Product intent", tested against new wishes.
4. **Constraints.** Privacy (no external LLM, data stays on the PC), hosting (the PC must be on), time to build. Any wish that breaks one gets reshaped or dropped early.

**Understand**
5. **Personas.** Felipe is the analyst. Is Lívia a logger only, or a viewer too, and what is *her* one number? Two personas can need different first screens (Our expenses vs My expenses, or a simpler home briefing).
6. **Moments of use.** When is the app opened: in a shop queue, on Sunday night, at the end of the month to settle up, when a bill arrives? Each moment wants a different first screen and a different depth.
7. **Time and device.** How long per visit, and on which device: phone over Tailscale, or laptop? Phone-first means one column, fewer controls, and answers before charts.
8. **Exploration or decision.** Does Felipe dig (filters, drill-downs) or glance and act? The answer decides whether to add depth or remove it.
9. **Talking it through.** Do the two of you sit down over money? If so, what should be on screen then? A shared, explainable view is not the same as the analyst's.
10. **What it replaced, and the pains left.** Spreadsheet, bank app, Tableau? What did that do better, and what still hurts? This is the guide's deliberate rephrasing of the purpose question: it surfaces what direct questions miss.

**Design**
11. **Should be / should not be.** In one sentence each. Ask it late: by then the answers are sharper than at the start.
12. **What each person sees.** Today, the shared views are common to both and personal ones are private. Should anything differ per person beyond that, such as a partner's personal total or only aggregates?
13. **Granularity.** The finest grain that matters: the expense, the day, the week, or the month? And the installment, by purchase month or by billing month? The answers decide what to aggregate and what the cashflow view should mean in the app.

**Data**
14. **What never reaches the app.** Cash, the partner's own-account payments for the house, bank fees, subscriptions on autopay. Roughly what share of a month? A large hole calls for a caveat on every total, or an import feature, before more charts.
15. **Freshness.** How long between paying and logging, and how often is a whole week backfilled? This decides whether "this month so far" can be trusted mid-month, and whether reminders are worth building.
16. **The rules behind the numbers.** Is the 3-month "usual month" the right baseline, or would the same month last year (13th salary, IPVA, Christmas), a target, or a rolling 12 months be better? Is the income-based split still right? Every KPI rests on one of these.

## Procedure

1. Read CLAUDE.md ("Product intent") and the reference, so you don't ask what's already settled.
2. Interview **one question at a time** (Felipe's preference). Pick it from the list above, leading with the ones whose answers would change the most, and phrase it around this app's own views and data.
3. After each answer, play back what you heard in a line or two, then pick the next question from that answer. A follow-up on something surprising beats the next item on the list.
4. End with the report, in plain text with no tables (Felipe's terminal garbles them): each finding with the answer behind it, what it changes (a view to add, cut or reshape, a rule to change, a caveat to show), and a suggested order. Don't implement anything unasked.
5. Save the durable answers (personas, moments of use, rules) as project memories, so later work doesn't ask again.

## The interview never closes

The formal interview is only the first pass. Every later input from Felipe is more interview material, and a cue to ask:

- **A criticism** ("this chart repeats the number", "too many clicks on the phone"). Connect it to what he already answered, then ask the question that answer leaves open. For example: "You said you check the phone for a quick scan. Is this chart failing that scan, or is it a laptop chart showing up on the phone?" A criticism usually means an earlier answer was incomplete, or the view drifted from it.
- **A request for a change** ("add X", "move Y"). Before building, place it against the earlier answers: which question does it serve, which persona and which moment of use? Does it fit the scope he set, or quietly widen it? If it contradicts an earlier answer, say so and ask which one holds now. The latest answer may well win, but say it aloud.
- **A reaction to something shipped** ("Lívia didn't find it", "I never open that tab"). Treat it as an answer to questions 2, 5 and 6, and ask what that implies for the view.

How to do it:

1. Read the saved interview answers first (the product-interview memory and any later ones), so the follow-up builds on them instead of asking again.
2. Ask **one** short question, quoting the earlier answer it connects to. Don't run a new full interview, and don't hold up a small, clear change for one: a question is worth asking when the answer would change what gets built.
3. When the answer refines or overturns an earlier one, update the memory. Keep the date, and what changed and why, so the history of his thinking stays readable.
