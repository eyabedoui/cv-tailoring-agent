"""C7: softer fabrication cases, each with a seeded example."""
from eval.fabrication import check_fabrication, check_soft_fabrication

MASTER = """# CV
## Experience
**Junior Developer**, Atlas Labs, 2022-2023
Built dashboards in Python.
**Intern**, Beacon Technologies, 2021
Wrote SQL reports.
## Education
Bachelor of Science in Computer Science, South Mediterranean University, 2024.
"""


def types(tailored):
    return {(f["type"], f["item"]) for f in check_soft_fabrication(MASTER, tailored)}


def test_honest_copy_is_clean():
    assert check_soft_fabrication(MASTER, MASTER) == []
    assert check_soft_fabrication(MASTER, MASTER + "\n## Objective\nApplying my skills.\n") == []


def test_inflated_level():
    assert ("level", "expert") in types(MASTER + "\nExpert in Python.\n")
    assert ("level", "senior") in types(MASTER.replace("Junior Developer", "Senior Developer"))


def test_invented_number():
    assert ("number", "40%") in types(MASTER + "\nImproved performance by 40%.\n")
    assert ("number", "5") in types(MASTER + "\n5 years of experience.\n")


def test_changed_date_not_in_master():
    assert ("date", "2019") in types(MASTER.replace("2022-2023", "2019-2023"))


def test_changed_date_wrong_employer():
    out = types(MASTER.replace("Atlas Labs, 2022-2023", "Atlas Labs, 2021-2023"))
    assert ("date", "2021 (Atlas Labs)") in out


def test_merged_roles():
    tailored = MASTER.replace("**Intern**, Beacon Technologies", "**Intern**, Atlas Labs")
    assert ("merged_role", "intern (Atlas Labs)") in types(tailored)


def test_check_fabrication_includes_soft_flags():
    flags = check_fabrication(MASTER, MASTER + "\nImproved performance by 40%.\n", missing_skills=[])
    assert {"type": "number", "item": "40%"} in flags


def test_soft_can_be_disabled():
    assert check_fabrication(MASTER, MASTER + "\nExpert in Python.\n", missing_skills=[], soft=False) == []
