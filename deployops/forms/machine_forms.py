"""Each machine's planned forms on a job (v2 Plan 3). Tasks 2 to 4 fill this module in."""


def on_submission_insert(doc, method=None) -> None:
	"""Form Submission `after_insert` hook. Task 3 links the submission to its machine's form row."""
