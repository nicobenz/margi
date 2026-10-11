# /margi respond <c17 c18 …>

Record the student's answers to grade comments. The answers are **theirs**: you collect them
and pass them on unchanged. You don't judge the comments here; the next grade does.

This command writes no draft and doesn't run `margi finalize`. The helper `uv run margi respond`
writes the record and commits it under the student's git identity.

## 1. Show the comments

Run `uv run margi comments` and find the numbers the student named. If they named none, ask
which comments they mean. Refuse numbers that aren't listed (closed or unknown) in one line.

## 2. Ask for each answer

Through the question tool, up to 4 comments per call. Question text: the comment's number and
one line of its body. Options:

- **Addressed**: the student changed the text and wants the next grade to check it.
- **Disputed**: the student thinks the comment is wrong. The next grade answers.
- **Won't fix**: the student decides to keep it as is. This closes the comment for good.
- **Skip for now**

Then, for each Disputed and Won't fix answer, ask for an optional reason in their own words
(answer via Other), with the options "No reason" and "Skip for now". An Addressed answer may
carry a reason too, if the student gives one unasked.

## 3. Confirm the exact words

Show the student exactly what will be recorded, reasons word for word, and ask: "Record these
answers?" with "Record" and "Change". **Never edit, shorten, translate, correct or paraphrase a
reason.** If the student's words are long, unclear or misspelled, they stay that way. Reasons
are at most 600 characters; if one is longer, ask the student to shorten it themselves.

## 4. Record

```sh
uv run margi respond c17=addressed c18=disputed c19=wont_fix --reason c18 "The term is defined in 1.2."
```

Statuses: `addressed`, `disputed`, `wont_fix`. Pass each reason exactly as confirmed, quoted
for the shell. If the helper refuses (a dirty tree, an unknown or closed comment), show its
message and stop.

Report in one line what was recorded, and that `/margi grade <section>` checks addressed and
disputed comments.
