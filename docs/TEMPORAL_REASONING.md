# Temporal reasoning

## Reference dates

Precedence is message/email timestamp, explicit document/transcript-date header, user source date, then import timestamp. Every candidate records the reference value and origin. A transcript cue offset such as 00:18:42 is kept as evidence; it is never treated as today's clock time.

## Deterministic resolution

The resolver uses Python datetime, ZoneInfo, dateutil and dateparser plus explicit rules. ISO dates always use YMD, regardless of the profile's numeric date preference. Slash dates use configured DMY/MDY. Named months, weekdays, today/tomorrow/day-after-tomorrow, relative days/weeks/months, noon/midnight and explicit clocks are supported.

“Next Friday” means Friday in the next Monday-starting week. An unqualified weekday means its next occurrence including the reference day. Missing years use the reference year with an explanation; a past result gets PAST_DATE_WARNING, not an automatic year increment.

The profile timezone defaults to Asia/Karachi. Named GMT/UTC/IANA zones convert to the profile zone. Ambiguous abbreviations such as CST require review. DST gaps and folds require review. Stored date/times contain offsets and events retain their IANA zone.

## Business dates, date-only values and ranges

EOD/COB must be configured; unset values create review warnings. Business days mean Monday–Friday, without a holiday calendar. First business day, last working day, beginning of next week, end of next month and first weekday of next month have deterministic rules.

Date-only commitments retain `time_unknown`; the all-day calendar representation is explicit. A configured deadline time is labeled as defaulted. Timed events use the configured duration when no end is given. Inclusive date ranges become exclusive all-day DTEND values, e.g. September 3–5 ends September 6.

## Ambiguity and context

“Sometime next week”, “around the 15th”, unresolved dependencies, ambiguous timezone abbreviations and bare “at 4” stay in NEEDS_REVIEW. Editing must supply valid explicit start/end details before approval and sync. The system does not silently infer PM from business context.

Historical language such as “took place” or “occurred” is excluded. Negated dates are not selected. Correction phrases choose the target date. Reschedules/cancellations propose changes against likely existing events; ambiguous matches require a target selection. Source evidence is never rewritten.

## Recurrence and dependencies

Common weekly, weekday, first-weekday monthly, month-day and explicit-start interval rules produce RRULEs. A recurrence with no anchor requires review. The dateutil recurrence engine expands occurrences for calendar display, reminders and bounded conflict detection.

“Two days before the interview” resolves only with one matching dated event. The derivation and target ID are retained. Otherwise the candidate stays unresolved. This is bounded deterministic relation detection, not a general dependency-language parser.

## Benchmark

`benchmarks/temporal_cases.json` has 68 explicit expected results. `scripts/benchmark.py` writes per-case expected/actual results. A 100% score means this authored regression suite passes; it does not claim 100% general extraction accuracy.

Dateparser configuration is based on its [official settings documentation](https://dateparser.readthedocs.io/en/stable/settings.html).
