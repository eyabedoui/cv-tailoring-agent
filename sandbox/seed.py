"""
Seed the sandbox with 25 fictional job postings (job_001 – job_025).

Usage:
    python -m sandbox.seed
    python sandbox/seed.py

All companies and contacts are entirely fictional.
No network access.  Writes JSON files to sandbox/postings/.

Expected match scores against master_cv.md (candidate_001) are listed in
docs/sandbox.md.  Scores assume simple substring matching (case-insensitive).
"""

import json
from pathlib import Path

_POSTINGS_DIR = Path(__file__).parent / "postings"

# ---------------------------------------------------------------------------
# 25 fictional postings — deterministic, never changing
# ---------------------------------------------------------------------------

POSTINGS: list[dict] = [
    {
        "job_id": "job_001",
        "title": "Junior AI Engineer",
        "company": "TechNova Solutions (fictional)",
        "requirements": ["Python", "machine learning", "Data analysis", "Problem solving"],
        "text": (
            "TechNova Solutions is building AI-driven analytics tools. "
            "We need a junior engineer who can wrangle data with Python, "
            "apply machine learning models, and communicate findings clearly. "
            "Strong problem solving and data analysis skills are essential."
        ),
    },
    {
        "job_id": "job_002",
        "title": "Full-Stack Web Developer",
        "company": "Brightware Labs (fictional)",
        "requirements": ["Python", "JavaScript", "React", "SQL"],
        "text": (
            "Brightware Labs builds internal tooling for logistics companies. "
            "We are hiring a full-stack developer comfortable with Python back-ends, "
            "React front-ends, SQL databases, and JavaScript throughout the stack."
        ),
    },
    {
        "job_id": "job_003",
        "title": "Systems Engineer",
        "company": "Ironclad Systems (fictional)",
        "requirements": ["Java", "C++", "Go", "Rust"],
        "text": (
            "Ironclad Systems develops embedded firmware for industrial hardware. "
            "Candidates must be fluent in Java, C++, Go, and Rust. "
            "Experience with low-latency systems is required."
        ),
    },
    {
        "job_id": "job_004",
        "title": "Data Analyst",
        "company": "Nexagen Analytics (fictional)",
        "requirements": ["Python", "SQL", "pandas", "NumPy"],
        "text": (
            "Nexagen Analytics provides business intelligence to retail clients. "
            "The data analyst role requires Python scripting, SQL querying, "
            "and hands-on work with pandas and NumPy for data wrangling."
        ),
    },
    {
        "job_id": "job_005",
        "title": "DevOps Engineer",
        "company": "Cloudrift Inc (fictional)",
        "requirements": ["Docker", "Kubernetes", "AWS", "Terraform"],
        "text": (
            "Cloudrift Inc manages cloud infrastructure for SaaS startups. "
            "The ideal candidate knows Docker, Kubernetes, AWS, and Terraform "
            "inside and out and can automate everything from CI pipelines to deployments."
        ),
    },
    {
        "job_id": "job_006",
        "title": "Frontend Developer",
        "company": "Prismix Design (fictional)",
        "requirements": ["JavaScript", "React", "HTML/CSS", "unit testing"],
        "text": (
            "Prismix Design creates accessible web interfaces for non-profit clients. "
            "We need a frontend developer skilled in JavaScript, React, and HTML/CSS "
            "who writes unit testing as a first-class practice."
        ),
    },
    {
        "job_id": "job_007",
        "title": "Backend Python Developer",
        "company": "Vortex Technologies (fictional)",
        "requirements": ["Python", "Flask", "REST APIs", "unit testing"],
        "text": (
            "Vortex Technologies delivers API-first products to fintech companies. "
            "We are looking for a Python developer experienced with Flask, "
            "REST APIs design, and writing comprehensive unit testing suites."
        ),
    },
    {
        "job_id": "job_008",
        "title": "Machine Learning Engineer",
        "company": "DeepMind Fictions (fictional)",
        "requirements": ["TensorFlow", "PyTorch", "Python", "deep learning"],
        "text": (
            "DeepMind Fictions is a research lab working on generative models. "
            "Candidates need TensorFlow, PyTorch, solid Python skills, and a "
            "background in deep learning theory and practice."
        ),
    },
    {
        "job_id": "job_009",
        "title": "Database Administrator",
        "company": "DataVault Corp (fictional)",
        "requirements": ["SQL", "MongoDB", "Redis", "Python"],
        "text": (
            "DataVault Corp manages multi-tenant data platforms for healthcare. "
            "The DBA role requires expertise in SQL relational databases, "
            "MongoDB document stores, Redis caching, and Python automation scripts."
        ),
    },
    {
        "job_id": "job_010",
        "title": "Big Data Engineer",
        "company": "StreamFlow Data (fictional)",
        "requirements": ["Spark", "Kafka", "Scala", "Python"],
        "text": (
            "StreamFlow Data processes billions of events per day for media companies. "
            "We need an engineer who understands Spark for batch processing, "
            "Kafka for streaming, and can write jobs in Scala and Python."
        ),
    },
    {
        "job_id": "job_011",
        "title": "Security Analyst",
        "company": "CipherShield Inc (fictional)",
        "requirements": ["Python", "Linux", "Bash", "problem solving"],
        "text": (
            "CipherShield Inc protects mid-market companies from cyber threats. "
            "The security analyst writes automation in Python and Bash, "
            "works daily on Linux servers, and brings sharp problem solving to incidents."
        ),
    },
    {
        "job_id": "job_012",
        "title": "Cloud Architect",
        "company": "NimbusCloud (fictional)",
        "requirements": ["AWS", "Azure", "Google Cloud Platform", "Terraform"],
        "text": (
            "NimbusCloud designs multi-cloud strategies for enterprise clients. "
            "Deep hands-on experience with AWS, Azure, Google Cloud Platform, "
            "and Terraform is mandatory for this senior architecture role."
        ),
    },
    {
        "job_id": "job_013",
        "title": "API Developer",
        "company": "ConnectAPI Corp (fictional)",
        "requirements": ["Python", "REST APIs", "Flask", "Git"],
        "text": (
            "ConnectAPI Corp builds integration middleware for e-commerce platforms. "
            "We need an API developer fluent in Python and Flask who designs "
            "clean REST APIs and maintains a tidy Git history."
        ),
    },
    {
        "job_id": "job_014",
        "title": "Research Software Engineer",
        "company": "OpenIntel Labs (fictional)",
        "requirements": ["Python", "pandas", "NumPy", "problem solving"],
        "text": (
            "OpenIntel Labs partners with universities on applied computing research. "
            "The role involves Python scripting, numerical computing with pandas "
            "and NumPy, and creative problem solving on novel data challenges."
        ),
    },
    {
        "job_id": "job_015",
        "title": "Technical Teaching Assistant",
        "company": "EduTech Corp (fictional)",
        "requirements": ["Python", "SQL", "communication", "teamwork"],
        "text": (
            "EduTech Corp runs online coding bootcamps. "
            "Teaching assistants guide learners through Python and SQL exercises, "
            "so strong communication and teamwork with the instructional staff are key."
        ),
    },
    {
        "job_id": "job_016",
        "title": "Stream Processing Developer",
        "company": "DataStream Processing (fictional)",
        "requirements": ["Scala", "Kafka", "Python", "Spark"],
        "text": (
            "DataStream Processing powers real-time analytics for insurance companies. "
            "The ideal candidate writes production Scala jobs, designs Kafka topics, "
            "and uses Python and Spark for rapid data exploration."
        ),
    },
    {
        "job_id": "job_017",
        "title": "Web Application Developer",
        "company": "CraftWeb Studio (fictional)",
        "requirements": ["JavaScript", "HTML/CSS", "React", "Node.js"],
        "text": (
            "CraftWeb Studio designs and builds websites for small businesses. "
            "We need a developer who is at home in JavaScript, HTML/CSS, "
            "React component libraries, and Node.js back-ends."
        ),
    },
    {
        "job_id": "job_018",
        "title": "Infrastructure Automation Engineer",
        "company": "GridCore (fictional)",
        "requirements": ["Docker", "Kubernetes", "Linux", "Bash"],
        "text": (
            "GridCore builds private-cloud solutions for manufacturing clients. "
            "The automation engineer containerises services with Docker and Kubernetes, "
            "manages Linux servers, and writes Bash scripts for operational tasks."
        ),
    },
    {
        "job_id": "job_019",
        "title": "GraphQL API Developer",
        "company": "QueryCraft (fictional)",
        "requirements": ["GraphQL", "JavaScript", "Node.js", "REST APIs"],
        "text": (
            "QueryCraft provides developer tooling for API-first teams. "
            "We need someone experienced with GraphQL schema design, "
            "JavaScript, Node.js server development, and REST APIs integration."
        ),
    },
    {
        "job_id": "job_020",
        "title": "Rust Systems Developer",
        "company": "LowLevel Labs (fictional)",
        "requirements": ["Rust", "C++", "Go", "Linux"],
        "text": (
            "LowLevel Labs writes performance-critical systems software. "
            "Candidates need expert Rust and C++ skills, working knowledge of Go, "
            "and comfort operating at the Linux kernel and userspace boundary."
        ),
    },
    {
        "job_id": "job_021",
        "title": "Junior Software Developer",
        "company": "StartBright Tech (fictional)",
        "requirements": ["Python", "SQL", "Git", "problem solving"],
        "text": (
            "StartBright Tech is a small product studio building SaaS tools. "
            "Our junior developer will write Python services, query SQL databases, "
            "contribute via Git, and tackle ambiguous problems with strong problem solving."
        ),
    },
    {
        "job_id": "job_022",
        "title": "AI Applications Developer",
        "company": "CogniApp (fictional)",
        "requirements": ["Python", "machine learning", "problem solving", "data analysis"],
        "text": (
            "CogniApp builds AI-powered productivity tools for knowledge workers. "
            "We need a developer who writes Python, can reason about machine learning "
            "pipelines, and brings rigorous problem solving and data analysis skills."
        ),
    },
    {
        "job_id": "job_023",
        "title": "Quality Assurance Engineer",
        "company": "QualityFirst Corp (fictional)",
        "requirements": ["Python", "unit testing", "Bash", "SQL"],
        "text": (
            "QualityFirst Corp embeds QA engineers into client development teams. "
            "The role involves writing Python test harnesses, automating checks with Bash, "
            "querying SQL databases to verify data integrity, and championing unit testing."
        ),
    },
    {
        "job_id": "job_024",
        "title": "Cloud-Native Developer",
        "company": "CloudSoft Inc (fictional)",
        "requirements": ["Python", "AWS", "React", "SQL"],
        "text": (
            "CloudSoft Inc migrates legacy systems to cloud-native architectures. "
            "The developer will write Python microservices, deploy to AWS, "
            "build React admin dashboards, and work with SQL databases daily."
        ),
    },
    {
        "job_id": "job_025",
        "title": "Data Science Intern",
        "company": "Insight Analytics (fictional)",
        "requirements": ["Python", "pandas", "NumPy", "SQL"],
        "text": (
            "Insight Analytics is a boutique consultancy delivering data stories to clients. "
            "The intern will process datasets in Python using pandas and NumPy, "
            "run SQL queries against client databases, and present findings to stakeholders."
        ),
    },
]


def seed(postings_dir: Path = _POSTINGS_DIR) -> None:
    """Write all postings as JSON files to postings_dir."""
    postings_dir.mkdir(parents=True, exist_ok=True)
    for posting in POSTINGS:
        path = postings_dir / f"{posting['job_id']}.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(posting, fh, indent=2, ensure_ascii=False)
    print(f"Seeded {len(POSTINGS)} postings to {postings_dir}")


if __name__ == "__main__":
    seed()
