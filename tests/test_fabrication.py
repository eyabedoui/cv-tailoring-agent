from eval.fabrication import check_fabrication, load_master_cv_text, load_missing_skills

MASTER = load_master_cv_text()


def kinds(items):
    return {(i["type"], i["item"].lower()) for i in items}


def test_honest_cv_has_no_flags():
    assert check_fabrication(MASTER, MASTER) == []


def test_added_kubernetes_is_flagged():
    items = check_fabrication(MASTER, MASTER + "\nSkills: Kubernetes, Docker\n")
    assert ("skill", "kubernetes") in kinds(items)
    assert ("skill", "docker") in kinds(items)


def test_java_is_not_confused_with_javascript():
    items = check_fabrication("Skills: Python", "Skills: Python, JavaScript")
    assert ("skill", "java") not in kinds(items)


def test_go_verb_is_not_the_language():
    assert check_fabrication("Skills: Python", "I go the extra mile with Python") == []


def test_invented_employer_is_flagged():
    items = check_fabrication(MASTER, MASTER + "\nSenior Engineer, Acme Technologies, 2022\n")
    assert ("employer", "acme technologies") in kinds(items)


def test_known_employers_in_master_are_fine():
    assert not [i for i in check_fabrication(MASTER, MASTER) if i["type"] == "employer"]


def test_allowed_employer_is_ignored():
    items = check_fabrication(MASTER, MASTER + "\nApplying to Acme Technologies\n", allowed=["Acme Technologies"])
    assert not [i for i in items if i["type"] == "employer"]


def test_invented_degree_is_flagged():
    items = check_fabrication(MASTER, MASTER + "\nMaster of Science in AI\n")
    assert ("degree", "master") in kinds(items)


def test_missing_skills_file_is_parsed_without_prose():
    skills = load_missing_skills()
    assert "Kubernetes" in skills and len(skills) >= 10
    assert all(len(s.split()) <= 4 and ":" not in s for s in skills)
