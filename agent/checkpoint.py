
"""
Human approval checkpoint for the CV-tailoring agent.

The checkpoint displays the proposed application and requires
explicit human approval before submission can proceed.
"""

import difflib


class HumanApprovalCheckpoint:
    def __init__(
        self,
        auto_approve=False,
        auto_reject=False,
        scripted_decisions=None,
        input_fn=input,
        output_fn=print,
    ):
        if auto_approve and auto_reject:
            raise ValueError(
                "auto_approve and auto_reject cannot both be enabled."
            )

        self.auto_approve = auto_approve
        self.auto_reject = auto_reject

        self.scripted_decisions = (
            list(scripted_decisions)
            if scripted_decisions is not None
            else None
        )

        self.input_fn = input_fn
        self.output_fn = output_fn

        # Stored for audit logging.
        self.last_review_text = None
        self.last_decision = None

    def build_review_text(
        self,
        job_title,
        company,
        job_id,
        master_cv,
        tailored_cv,
        cover_letter,
    ):
        """Build the complete human-review message."""

        diff = difflib.unified_diff(
            master_cv.splitlines(),
            tailored_cv.splitlines(),
            fromfile="master_cv",
            tofile="tailored_cv",
            lineterm="",
        )

        diff_lines = list(diff)

        added_lines = [
            line for line in diff_lines
            if line.startswith("+") and not line.startswith("+++")
        ]

        removed_lines = [
            line for line in diff_lines
            if line.startswith("-") and not line.startswith("---")
        ]

        diff_text = "\n".join(diff_lines) or "No CV changes."

        added_text = "\n".join(added_lines) or "None"
        removed_text = "\n".join(removed_lines) or "None"

        return (
            f"APPLICATION REVIEW\n"
            f"==================\n"
            f"Job: {job_title}\n"
            f"Company: {company}\n"
            f"Job ID: {job_id}\n\n"
            f"CV DIFFERENCE\n"
            f"-------------\n"
            f"{diff_text}\n\n"
            f"ADDED LINES\n"
            f"-----------\n"
            f"{added_text}\n\n"
            f"REMOVED LINES\n"
            f"-------------\n"
            f"{removed_text}\n\n"
            f"COVER LETTER\n"
            f"------------\n"
            f"{cover_letter}\n\n"
            f"Submit these files to job {job_id}?"
        )

    def _get_decision(self):
        """Obtain an approval decision from the configured mode."""

        if self.auto_approve:
            return True

        if self.auto_reject:
            return False

        if self.scripted_decisions is not None:
            if not self.scripted_decisions:
                raise RuntimeError(
                    "No scripted approval decisions remain."
                )

            decision = self.scripted_decisions.pop(0)

            if not isinstance(decision, bool):
                raise ValueError(
                    "Scripted decisions must be True or False."
                )

            return decision

        while True:
            answer = self.input_fn(
                "Approve submission? Enter yes or no: "
            ).strip().lower()

            if answer in ("yes", "y"):
                return True

            if answer in ("no", "n"):
                return False

            self.output_fn("Please enter yes or no.")

    def request_approval(
        self,
        job_title,
        company,
        job_id,
        master_cv,
        tailored_cv,
        cover_letter,
    ):
        """
        Display the application review and obtain human approval.

        Returns:
            True: Human approved submission.
            False: Human rejected submission.
        """

        review_text = self.build_review_text(
            job_title=job_title,
            company=company,
            job_id=job_id,
            master_cv=master_cv,
            tailored_cv=tailored_cv,
            cover_letter=cover_letter,
        )

        # Store the exact review for the execution log.
        self.last_review_text = review_text

        self.output_fn(review_text)

        approved = self._get_decision()

        # Store the decision for audit logging.
        self.last_decision = approved

        decision_text = "APPROVED" if approved else "REJECTED"

        self.output_fn(f"Human decision: {decision_text}")

        return approved
