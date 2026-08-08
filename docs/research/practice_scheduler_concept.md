# Practice Scheduler Concept

**Status:** Approved mathematical and scientific contract

**Scheduler version:** `gustav-practice-v1`

**Date:** 4 August 2026

**Product approval:** 8 August 2026

**Applies to:** GUSTAV practice and review tasks

## 1. Purpose

This document defines the first version of GUSTAV's scheduler for practice and review tasks. It is the authoritative contract for the mathematical model, its global parameters, its time semantics, and its expected outputs.

The scheduler has one operational goal: after every valid practice attempt, determine one exact future instant at which the same task becomes due again. It must remain simple enough for teachers, learners, and maintainers to understand, while still using the information that GUSTAV actually observes:

- the learner's previous stability for the task,
- the time elapsed since the preceding valid attempt,
- the resulting estimated retrievability,
- the continuous fulfillment value `e`,
- the visible classification,
- and whether the attempt was supported.

The model is deterministic. The language model does not choose an interval, classification, or parameter. Given the same validated input and scheduler version, every implementation must produce the same result.

## 2. Evidence and limits of the evidence

### 2.1 Research-supported design principles

The scheduler rests on the following reasonably well-supported principles:

1. Retrieval practice improves long-term retention more reliably than passive restudy. Corrective feedback is particularly useful after an unsuccessful retrieval attempt.
2. Practice distributed across separate sessions supports longer retention than the same amount of massed practice. Repeated recall within one short period is not a substitute for later relearning.
3. The useful spacing gap depends on the intended retention horizon. Research does not establish one universal sequence of fixed intervals.
4. A successful retrieval after a longer delay is more informative than an equally successful retrieval made while the answer is still highly accessible. Conversely, an early failure is stronger negative evidence than a failure after a very long delay.
5. Expanding intervals are a plausible consequence of increasing memory stability, but an expanding schedule is not itself a universally superior empirical rule.

These principles are consistent with research on retrieval practice, spacing, successive relearning, and trainable memory models. They justify the architecture of a time-aware stability model, but not the exact constants selected below.

### 2.2 GUSTAV-specific pilot hypotheses

The following choices are transparent engineering hypotheses for the first pilot, not established psychological laws:

- the fixed shape of the forgetting curve,
- a target retention of `0.90`,
- the exact growth and reduction equations,
- the use of the rubric-derived fulfillment value `e` as continuous evidence about response quality,
- the 24-hour boundary for a stability-increasing retrieval,
- and the selected reduction strength.

In particular, `e = 0.80` means that the submitted answer fulfilled 80% of the evaluation criteria or available points. It does **not** mean that the learner has an 80% probability of recalling the answer in the future. Retrievability `R` and fulfillment `e` have different meanings and must remain separate in code, audit data, and user-facing explanations.

## 3. Model selection

| Model | Advantages | Reasons not selected for version 1 |
| --- | --- | --- |
| Fixed intervals or SM-2-style steps | Very easy to implement and explain | Fixed steps discard the actual elapsed time and GUSTAV's continuous fulfillment value; SM-2 parameters are heuristic and rely on learner ratings that GUSTAV does not collect |
| Half-Life Regression | Uses a clear forgetting curve and can learn from production data | Its useful feature weights require an adequate training dataset; the published model primarily uses binary language-learning outcomes |
| Full FSRS | Models difficulty, stability, and retrievability and can be fitted to review histories | Current FSRS variants use many fitted parameters and four learner ratings; directly mapping GUSTAV's automatic three-level classification onto those ratings would add unjustified complexity |
| Reduced GUSTAV stability model | Keeps one persistent memory variable, uses exact elapsed time and `e`, and remains fully auditable | The initial parameters are pilot assumptions and must be evaluated with GUSTAV data |

GUSTAV therefore adopts a reduced, one-state stability model inspired by DSR-style models. It borrows the useful semantics of stability and retrievability without claiming to be FSRS or a fitted derivative of FSRS.

## 4. Terms and inputs

### 4.1 Persistent state

For each course, learner, and practice task, the scheduler stores a stability `S` in days. `S` is the interval at which the selected forgetting curve reaches the target retention `r = 0.90`.

The surrounding practice state also records at least:

- the exact current `due_at`,
- the last rounded interval,
- the time of the preceding valid completed attempt,
- the last fulfillment and classification,
- the scheduler version,
- and an audit trail of every attempted transition.

The preceding-attempt timestamp advances after every valid completed attempt, including supported attempts and mastered attempts within 24 hours. This acknowledges the latest exposure when the next elapsed time is calculated, even when stability and the existing due date intentionally remain unchanged.

### 4.2 Attempt inputs

Each scheduler evaluation receives:

- `completed_at`: an aware UTC instant,
- `e`: a finite fulfillment value in the closed interval `[0, 1]`,
- `classification`: `mastered`, `partial`, or `insufficient`,
- `supported_recall`: whether the answer followed access to a solution or mandatory support,
- and the previous practice state, if one exists.

The application derives classifications before calling the scheduler:

| Evaluation source | `mastered` | `partial` | `insufficient` |
| --- | --- | --- | --- |
| Native rubric | `e >= 0.85` | `0.40 <= e < 0.85` | `e < 0.40` |
| H5P score | `e = 1` | `0 < e < 1` | `e = 0` |

For an unsupported attempt, the classification must match this table exactly. For a supported attempt, the workflow applies the same rules and then caps an otherwise `mastered` result to `partial`: a supported native result is `partial` at `e >= 0.40`, and a supported H5P result is `partial` at `e > 0`. The scheduler ignores the resulting classification and fulfillment for stability changes because support makes the attempt unsuitable as an independent retrieval measurement.

### 4.3 Time quantities

All calculations use elapsed SI seconds and `86,400` seconds per model day:

\[
t=\frac{completed\_at-last\_attempt\_at}{86\,400}.
\]

The scheduler does not use calendar dates, local midnight, or daylight-saving-time transitions. An elapsed duration below exactly 86,400 seconds is "within 24 hours". An elapsed duration of exactly 86,400 seconds is eligible for stability growth.

## 5. Versioned constants

| Symbol or name | Value | Meaning |
| --- | ---: | --- |
| `scheduler_version` | `gustav-practice-v1` | Identifies this complete parameter and equation set |
| `r` | `0.90` | Target retention |
| `SECONDS_PER_DAY` | `86,400` | Duration of one model day |
| `S_min` | `1` day | Smallest regular interval and stability |
| `S_max` | `36,525` days | 100-year technical safety ceiling |
| `initial_base` | `2` | Base of the initialization equation |
| `mastery_gain_scale` | `1` | Makes full on-time mastery double stability |
| `loss_scale` | `2` | Selected medium reduction strength |

`S_max` prevents timestamp overflow and non-operational values. It is not intended as a pedagogically meaningful maximum. Reaching it would require an unrealistically long sequence of successful reviews over more than a human lifetime.

Any change to an equation, constant, rounding rule, classification contract, or no-op rule creates a new scheduler version.

## 6. Mathematical contract

### 6.1 Forgetting curve

For an existing state, estimated retrievability after `t` days is:

\[
R(t,S)=\left(1+\frac{t}{9S}\right)^{-1}.
\]

The inverse interval function for a target retention `r` is:

\[
I(r,S)=9S\left(\frac{1}{r}-1\right).
\]

With `r = 0.90`:

\[
I(0.90,S)=S.
\]

This identity is one reason for using the 90%-stability definition: the stored stability directly describes the next unrounded interval.

### 6.2 Initialization

A new task has no prior elapsed interval from which retrievability could be inferred. Its initial stability is therefore seeded solely from the first independent result:

\[
q=\begin{cases}
1 & \text{if classification is mastered},\\
e & \text{otherwise},
\end{cases}
\qquad
S_{raw}=2^q.
\]

Thus a fully or securely mastered new task starts at two days. Other results vary continuously from one to fewer than two days. A supported first attempt is invalid because the solution is unavailable before the first completed attempt.

### 6.3 No-op evidence cases

Two cases do not change stability or the existing due date:

1. `supported_recall` is true, regardless of `e` or classification.
2. The attempt is `mastered`, but `t < 1` day.

For both cases:

\[
S_{new}=S,
\qquad
due\_at_{new}=due\_at_{old}.
\]

The attempt remains part of the immutable history, and the preceding-attempt timestamp advances to `completed_at`. A subsequent attempt therefore measures elapsed time from this latest exposure. The existing rounded interval and due instant remain unchanged.

If the retained due instant is already in the past, the task remains due. The session layer prevents an unbounded immediate loop inside the current session; the scheduler does not silently postpone an overdue task on the basis of supported or too-early positive evidence.

An independent `partial` or `insufficient` attempt within 24 hours is not a no-op. An early failure is relevant negative evidence and uses the reduction equation below.

### 6.4 Independent mastered retrieval

For an independent `mastered` attempt with `t >= 1`:

\[
S_{raw}
=S\left(1+e\frac{1-R}{1-r}\right).
\]

The fraction

\[
\frac{1-R}{1-r}
\]

expresses retrieval difficulty relative to an on-time review. It equals `1` when `R = r`, is below `1` for an early review, and is above `1` for a late review.

Consequently:

- a fully correct on-time retrieval doubles stability,
- an early retrieval increases stability less,
- a late successful retrieval increases stability more,
- and `e` differentiates the strength of mastered native answers.

### 6.5 Partial or insufficient retrieval

For an independent `partial` or `insufficient` attempt, first calculate the timing-sensitive reduction exponent:

\[
p(R)=2\left(1+\frac{R}{r}\right).
\]

Then calculate:

\[
S_{raw}=1+(S-1)e^{p(R)}.
\]

This equation has useful explicit boundaries:

- `e = 0` resets stability to one day,
- `0 < e < 1` retains a fulfillment-dependent fraction of stability above one day,
- a higher `e` always retains more stability,
- an early failure has a larger exponent and therefore reduces stability more strongly,
- and even a very late failure still reduces stability because `p(R)` remains at least `2`.

The thresholds at `e = 0.40` affect only the visible distinction between `partial` and `insufficient`. Both use the same continuous reduction equation. The Mastery threshold is intentionally a hard scheduling boundary: just below it, stability decreases; at or above it, an independent delayed retrieval uses the growth equation.

### 6.6 Clamping, interval, and due instant

For every state-changing result:

\[
S_{new}=\min\left(S_{max},\max\left(S_{min},S_{raw}\right)\right).
\]

The exact positive interval in seconds is calculated after clamping:

\[
interval\_seconds
=\operatorname{round}_{half\_up}(86\,400S_{new}).
\]

For positive values, half-up rounding is equivalent to:

\[
\operatorname{round}_{half\_up}(x)=\lfloor x+0.5\rfloor.
\]

The due instant is:

\[
due\_at=completed\_at+interval\_seconds.
\]

`due_at` remains a precise UTC timestamp. It is never rounded to an hour, date, local midnight, or school day. If an `interval_days` field is persisted for audit purposes, it is the exact scheduled duration `interval_seconds / 86,400`; it need not be numerically identical to the unrounded `S_new`.

## 7. Evaluation order and failure behaviour

An implementation must apply this order:

1. Validate timestamps, fulfillment, classification consistency, support state, previous stability, previous due date, and scheduler version.
2. For a new task, apply initialization.
3. For an existing task, calculate `t` and reject negative elapsed time.
4. Calculate `R` and reject a non-finite result.
5. Apply the supported-attempt no-op before evaluating classification.
6. Apply the within-24-hours mastered no-op.
7. Apply either the mastered-growth or non-mastery-reduction equation.
8. Reject non-finite intermediate results; do not convert infinity into `S_max`.
9. Clamp finite stability, round the interval, and calculate `due_at`.
10. Persist the attempt audit and state mutation atomically and idempotently.

Validation or arithmetic failure produces no classification-driven scheduler mutation. The attempt remains in its appropriate technical error state, and the previous stability, interval, due date, preceding-attempt timestamp, review count, and scheduler version remain unchanged.

## 8. Worked examples

### 8.1 New partial answer

For a new native task with `e = 0.60` and classification `partial`:

\[
S_0=2^{0.60}=1.515716567\text{ days}.
\]

The rounded interval is 130,958 seconds, or 1 day, 12 hours, 22 minutes, and 38 seconds.

### 8.2 Full retrieval exactly when due

Given `S = 30` days and `t = 30` days:

\[
R=0.90.
\]

For `e = 1` and `mastered`:

\[
S_{new}=30\left(1+1\cdot\frac{1-0.90}{1-0.90}\right)=60\text{ days}.
\]

### 8.3 Early and late mastered retrievals

With the same `S = 30` days and `e = 1`:

| Actual elapsed time | `R` | `S_new` |
| ---: | ---: | ---: |
| 3 days | 0.989010989 | 33.296703297 days |
| 15 days | 0.947368421 | 45.789473684 days |
| 30 days | 0.900000000 | 60.000000000 days |
| 60 days | 0.818181818 | 84.545454545 days |
| 300 days | 0.473684211 | 187.894736842 days |

The three-day example assumes the preceding valid attempt was at least 24 hours earlier. An elapsed duration below 24 hours would invoke the no-op rule instead.

### 8.4 On-time non-mastery

Given `S = 30` days and `R = 0.90`, the selected exponent is `p = 4`:

| `e` | Classification range | `S_new` |
| ---: | --- | ---: |
| 0.00 | insufficient | 1.000000000 day |
| 0.20 | insufficient | 1.046400000 days |
| 0.39 | insufficient | 1.670898210 days |
| 0.40 | partial | 1.742400000 days |
| 0.60 | partial | 4.758400000 days |
| 0.84 | partial for a native task | 15.438268960 days |

### 8.5 Same-session correction

A new task receives `e = 0.60`, so it is initialized with `S = 1.515716567` days and a corresponding due instant. The learner then answers it correctly during the same session. Because fewer than 24 hours have elapsed, the mastered retry does not alter either stability or the existing due instant. The next independent delayed retrieval can increase stability.

### 8.6 Supported recall

If a learner views the model solution and then submits an answer, the attempt is recorded as supported. Stability and the previous due instant remain unchanged. The preceding-attempt timestamp advances, ensuring that a later successful independent answer is not incorrectly treated as if no exposure had occurred in the meantime.

## 9. Typical trajectories

The following trajectories assume that every state-changing attempt occurs exactly when due unless stated otherwise.

| Scenario | Stability sequence in days |
| --- | --- |
| New, then repeatedly fully mastered | `2 → 4 → 8 → 16 → 32 → 64 → 128` |
| `S = 30`, then `e = 0`, followed by full mastery | `30 → 1 → 2 → 4 → 8` |
| `S = 30`, then `e = 0.60`, followed by full mastery | `30 → 4.7584 → 9.5168 → 19.0336` |
| New `e = 0.60`, corrected in the same session, then fully mastered when due | `1.515716567 → 1.515716567 → 3.031433134` |
| Supported attempt while `S = 30` | `30 → 30`, with the existing due instant unchanged |

These are organizational predictions of the selected model, not claims that every learner's memory follows these exact values.

## 10. Sensitivity analysis

### 10.1 Reduction strength

The general comparison family is:

\[
p_k(R)=k\left(1+\frac{R}{r}\right).
\]

For `S = 30` and an on-time attempt, the alternatives produce:

| Reduction | `k` | `e = 0.84` | `e = 0.60` | `e = 0.40` |
| --- | ---: | ---: | ---: | ---: |
| Mild | 1 | 21.462400000 | 11.440000000 | 5.640000000 |
| **Selected medium** | **2** | **15.438268960** | **4.758400000** | **1.742400000** |
| Strong | 3 | 11.187642917 | 2.353024000 | 1.118784000 |

The medium variant preserves meaningful distinctions within partial answers while returning substantial gaps quickly. The parameter is a pilot choice and is eligible for later calibration.

### 10.2 Mastery growth

For a full on-time retrieval from `S = 30`, candidate mastery gain scales of `0.5`, `1`, and `1.5` produce 45, 60, and 75 days respectively. Version 1 selects scale `1`, making the central behaviour a transparent doubling.

### 10.3 Target retention

Keeping the same 90%-stability `S`, the inverse curve gives:

| Target retention | Interval as a multiple of `S` |
| ---: | ---: |
| 0.85 | 1.588235294 |
| **0.90** | **1.000000000** |
| 0.95 | 0.473684211 |

Higher target retention substantially increases review frequency. Version 1 fixes `r = 0.90`; teachers and learners cannot configure it.

## 11. Golden Vectors

These vectors are normative. Implementations must use IEEE-754 binary64 arithmetic for the model equations, clamp before interval conversion, and use positive half-up rounding to whole seconds. Stability comparisons use a tolerance of `1e-9` days; interval seconds and due instants must match exactly.

Unless a row states otherwise, the base instant and preceding valid attempt are `2026-08-04T08:00:00Z`. A previous `due_at` equals the base instant plus the previous rounded interval.

| # | Case | Previous `S` | `completed_at` / elapsed | `e` | Classification | `R` | Expected `S_new` | Interval seconds | Expected `due_at` | Result |
| ---: | --- | ---: | --- | ---: | --- | ---: | ---: | ---: | --- | --- |
| 1 | New, zero fulfillment | — | `2026-08-04T08:00:00Z` | 0.00 | insufficient | — | 1.000000000 | 86,400 | `2026-08-05T08:00:00Z` | initialize |
| 2 | New, partial boundary | — | `2026-08-04T08:00:00Z` | 0.40 | partial | — | 1.319507911 | 114,005 | `2026-08-05T15:40:05Z` | initialize |
| 3 | New, high partial | — | `2026-08-04T08:00:00Z` | 0.84 | partial | — | 1.790050142 | 154,660 | `2026-08-06T02:57:40Z` | initialize |
| 4 | New, native Mastery boundary | — | `2026-08-04T08:00:00Z` | 0.85 | mastered | — | 2.000000000 | 172,800 | `2026-08-06T08:00:00Z` | initialize |
| 5 | New, H5P high partial | — | `2026-08-04T08:00:00Z` | 0.99 | partial | — | 1.986184991 | 171,606 | `2026-08-06T07:40:06Z` | initialize |
| 6 | Full retrieval when due | 2 | 2 days | 1.00 | mastered | 0.900000000 | 4.000000000 | 345,600 | `2026-08-10T08:00:00Z` | update |
| 7 | Full retrieval at exactly 24 hours | 2 | 1 day | 1.00 | mastered | 0.947368421 | 3.052631579 | 263,747 | `2026-08-08T09:15:47Z` | update |
| 8 | Full retrieval after 12 hours | 2 | 12 hours | 1.00 | mastered | 0.972972973 | 2.000000000 | unchanged: 172,800 | unchanged: `2026-08-06T08:00:00Z` | 24-hour no-op |
| 9 | On-time partial | 30 | 30 days | 0.60 | partial | 0.900000000 | 4.758400000 | 411,126 | `2026-09-08T02:12:06Z` | update |
| 10 | On-time zero fulfillment | 30 | 30 days | 0.00 | insufficient | 0.900000000 | 1.000000000 | 86,400 | `2026-09-04T08:00:00Z` | update |
| 11 | Early partial | 30 | 3 days | 0.60 | partial | 0.989010989 | 4.397197761 | 379,918 | `2026-08-11T17:31:58Z` | update |
| 12 | Very late full retrieval | 30 | 300 days | 1.00 | mastered | 0.473684211 | 187.894736842 | 16,234,105 | `2027-12-05T05:28:25Z` | update |
| 13 | Supported partial when due | 30 | 30 days | 0.60 | partial | 0.900000000 | 30.000000000 | unchanged: 2,592,000 | unchanged: `2026-09-03T08:00:00Z` | supported no-op |
| 14 | Technical ceiling | 30,000 | 30,000 days; `2108-09-23T08:00:00Z` | 1.00 | mastered | 0.900000000 | 36,525.000000000 | 3,155,760,000 | `2208-09-24T08:00:00Z` | clamp |
| 15 | Invalid fulfillment | 2 | 3 days | 1.01 | mastered | — | unchanged: 2.000000000 | unchanged: 172,800 | unchanged: `2026-08-06T08:00:00Z` | reject without mutation |

For rows 6–8, `completed_at` is the base instant plus the stated elapsed time. For rows 9, 10, and 13 it is `2026-09-03T08:00:00Z`; for row 11 it is `2026-08-07T08:00:00Z`; and for row 12 it is `2027-05-31T08:00:00Z`.

Rows 8 and 13 advance the preceding-attempt timestamp to their respective `completed_at` despite retaining the schedule. Row 15 does not advance any state or metadata because validation fails.

## 12. Required properties and edge cases

Automated tests must establish at least these properties:

1. Initialization is monotonic in `e`, remains within `[1, 2]`, and yields exactly two days for every valid `mastered` first attempt.
2. For independent delayed Mastery, `S_new` is non-decreasing in `e` and elapsed time and never below `S`.
3. For non-mastery, `S_new` is non-decreasing in `e`, remains within `[1, S]`, and equals one day at `e = 0`.
4. For the same `S` and `e < 1`, an earlier non-mastery result reduces stability at least as strongly as a later result.
5. Supported attempts never change stability, interval, or due date.
6. Mastered attempts at `t < 1` day never change stability, interval, or due date; the same input at exactly one day uses the growth equation.
7. No state-changing result produces a stability below one day or above 36,525 days.
8. No calendar or local-time conversion influences the result.
9. Invalid, non-finite, inconsistent, out-of-order, duplicated, or technically failed inputs cannot partially update scheduler state.
10. Replaying the same idempotent completion produces exactly one audit record and at most one state transition.

Classification boundary tests must cover values immediately below, exactly at, and immediately above `0.40` and `0.85`, plus H5P values `0`, a strict fraction, and `1`.

## 13. Version migration

Scheduler constants are global and immutable within a version. When a future version is introduced:

- existing `S` values remain meaningful because every version uses the documented 90%-stability semantics unless a migration explicitly says otherwise,
- existing `due_at` values are not changed retrospectively,
- the next state-changing independent attempt uses the newly activated version,
- that transition records both the prior state and the new scheduler version,
- and audit or evaluation queries must never mix versions without grouping them explicitly.

No background rescheduling is part of version 1.

## 14. Pilot evaluation and parameter governance

### 14.1 Eligible observations

Scheduler calibration uses only independent attempts made at least 24 hours after the preceding valid attempt. Supported attempts, same-session corrections, technical failures, duplicated completions, and inconsistent classifications are excluded.

For each eligible attempt, retain the scheduler version, prior `S`, elapsed time, predicted `R`, `e`, classification, task format, original due instant, and resulting state. Raw student answers are not required for scheduler calibration and should not be copied into analytics exports.

The binary calibration target is whether the independent attempt was `mastered`. Because native and H5P tasks use different Mastery thresholds, calibration and Brier scores are calculated separately by evaluation source and combined only as a macro-average. The continuous `e` distribution is analysed separately and must not be treated as observed recall probability.

### 14.2 Minimum evidence before changing parameters

No global parameter change is considered before the pilot contains at least:

- 500 eligible delayed transitions,
- 30 distinct learners,
- 20 distinct tasks,
- and adequate representation of native and H5P tasks if conclusions are intended to apply to both.

No single learner or task should contribute more than 10% of the calibration sample. If this balance condition cannot be met, results remain descriptive and do not justify a global parameter change.

### 14.3 Decision rule

A candidate parameter set may replace the current one only when all of the following hold:

1. Learner-clustered bootstrap resampling gives a 95% confidence interval for the candidate's Brier-score improvement that lies entirely above zero.
2. The relative Brier-score improvement is at least 5% on held-out chronological data.
3. Calibration plots show that the improvement is not produced by one task, format, or narrow retrievability band.
4. Offline schedule replay estimates no more than a 10% increase in expected due-task workload.
5. A sampled teacher review finds the upstream rubric evaluation sufficiently reliable; scheduler tuning must not compensate for systematic scoring defects.
6. The equations remain simple enough to document with the same level of transparency as this version.

Every accepted change receives a new version, updated Golden Vectors, a documented comparison, and explicit product approval. Parameters are not fitted per learner in version 1.

## 15. Limitations

- Repeating the same teacher-authored task measures increasingly reliable retrieval of that task, not transfer to novel situations.
- One stability value cannot represent every underlying concept or criterion inside a complex task.
- Equal-weight rubric averages can hide a missing essential criterion. That is an assessment-design issue and must not be repaired implicitly by the scheduler.
- The fixed forgetting curve and global parameters may fit some ages, subjects, and task formats better than others.
- AI evaluation noise near the hard Mastery boundary can produce substantially different intervals. Classification reliability must therefore be monitored before scheduler parameters are tuned.
- A due instant is a recommendation, not a guarantee that a learner will practise at that instant. The elapsed-time equations intentionally handle early and delayed reviews.

## 16. References

- Cepeda, N. J., Vul, E., Rohrer, D., Wixted, J. T., & Pashler, H. (2008). *Spacing effects in learning: A temporal ridgeline of optimal retention*. Psychological Science, 19(11), 1095–1102. <https://doi.org/10.1111/j.1467-9280.2008.02209.x>
- Kang, S. H. K., Lindsey, R. V., Mozer, M. C., & Pashler, H. (2014). *Retrieval practice over the long term: Should spacing be expanding or equal-interval?* Psychonomic Bulletin & Review, 21, 1544–1550. <https://pubmed.ncbi.nlm.nih.gov/24744260/>
- Pashler, H., Cepeda, N. J., Wixted, J. T., & Rohrer, D. (2005). *When does feedback facilitate learning of words?* Journal of Experimental Psychology: Learning, Memory, and Cognition, 31(1), 3–8. <https://pubmed.ncbi.nlm.nih.gov/15641900/>
- Rawson, K. A., & Dunlosky, J. (2022). *Successive relearning: An underexplored but potent technique for obtaining and maintaining knowledge*. Current Directions in Psychological Science, 31(4), 362–368. <https://doi.org/10.1177/09637214221100484>
- Rawson, K. A., Vaughn, K. E., Walsh, M., & Dunlosky, J. (2018). *Investigating and explaining the effects of successive relearning on long-term retention*. Journal of Experimental Psychology: Applied, 24(1), 57–71. <https://pubmed.ncbi.nlm.nih.gov/29431462/>
- Settles, B., & Meeder, B. (2016). *A trainable spaced repetition model for language learning*. Proceedings of ACL 2016, 1848–1858. <https://aclanthology.org/P16-1174/>
- Ye, J., Su, J., & Cao, Y. (2022). *A stochastic shortest path algorithm for optimizing spaced repetition scheduling*. Proceedings of KDD 2022, 4381–4390. <https://dl.acm.org/doi/10.1145/3534678.3539081>
- Open Spaced Repetition. *The Algorithm: FSRS*. <https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm/5bf70e459e45152d40988c670fa7c4625b5e8577>
- Wozniak, P. A. *Application of a computer to improve the results obtained in working with the SuperMemo method: SM-2*. <https://super-memory.org/archive/english/ol/sm2.htm>

## 17. Approval gate

The product owner approved this complete contract on 8 August 2026, including its equations, constants, Golden Vectors, and pilot-governance rules. Scheduler Gate 0 is therefore closed. Any semantic change still requires a new scheduler version and explicit product approval.
