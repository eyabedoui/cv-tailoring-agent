# Sandbox job postings

25 fictional postings (job_001 – job_025).  All companies are invented;
all contacts use `example.invalid` domains.  No real data, no network access.

Expected match scores are computed by the stub `match_skills` implementation
(simple case-insensitive substring matching against `master_cv.md`).

| job_id  | Title                             | Company                           | Requirements                                            | Expected score |
|---------|-----------------------------------|-----------------------------------|---------------------------------------------------------|----------------|
| job_001 | Junior AI Engineer                | TechNova Solutions (fictional)    | Python, machine learning, Data analysis, Problem solving | 0.75           |
| job_002 | Full-Stack Web Developer          | Brightware Labs (fictional)       | Python, JavaScript, React, SQL                          | 1.00           |
| job_003 | Systems Engineer                  | Ironclad Systems (fictional)      | Java, C++, Go, Rust                                     | 0.00           |
| job_004 | Data Analyst                      | Nexagen Analytics (fictional)     | Python, SQL, pandas, NumPy                              | 1.00           |
| job_005 | DevOps Engineer                   | Cloudrift Inc (fictional)         | Docker, Kubernetes, AWS, Terraform                      | 0.00           |
| job_006 | Frontend Developer                | Prismix Design (fictional)        | JavaScript, React, HTML/CSS, unit testing               | 1.00           |
| job_007 | Backend Python Developer          | Vortex Technologies (fictional)   | Python, Flask, REST APIs, unit testing                  | 1.00           |
| job_008 | Machine Learning Engineer         | DeepMind Fictions (fictional)     | TensorFlow, PyTorch, Python, deep learning              | 0.25           |
| job_009 | Database Administrator            | DataVault Corp (fictional)        | SQL, MongoDB, Redis, Python                             | 0.50           |
| job_010 | Big Data Engineer                 | StreamFlow Data (fictional)       | Spark, Kafka, Scala, Python                             | 0.25           |
| job_011 | Security Analyst                  | CipherShield Inc (fictional)      | Python, Linux, Bash, problem solving                    | 1.00           |
| job_012 | Cloud Architect                   | NimbusCloud (fictional)           | AWS, Azure, Google Cloud Platform, Terraform            | 0.00           |
| job_013 | API Developer                     | ConnectAPI Corp (fictional)       | Python, REST APIs, Flask, Git                           | 1.00           |
| job_014 | Research Software Engineer        | OpenIntel Labs (fictional)        | Python, pandas, NumPy, problem solving                  | 1.00           |
| job_015 | Technical Teaching Assistant      | EduTech Corp (fictional)          | Python, SQL, communication, teamwork                    | 1.00           |
| job_016 | Stream Processing Developer       | DataStream Processing (fictional) | Scala, Kafka, Python, Spark                             | 0.25           |
| job_017 | Web Application Developer         | CraftWeb Studio (fictional)       | JavaScript, HTML/CSS, React, Node.js                    | 1.00           |
| job_018 | Infrastructure Automation Engineer| GridCore (fictional)              | Docker, Kubernetes, Linux, Bash                         | 0.50           |
| job_019 | GraphQL API Developer             | QueryCraft (fictional)            | GraphQL, JavaScript, Node.js, REST APIs                 | 0.75           |
| job_020 | Rust Systems Developer            | LowLevel Labs (fictional)         | Rust, C++, Go, Linux                                    | 0.25           |
| job_021 | Junior Software Developer         | StartBright Tech (fictional)      | Python, SQL, Git, problem solving                       | 1.00           |
| job_022 | AI Applications Developer         | CogniApp (fictional)              | Python, machine learning, problem solving, data analysis| 0.75           |
| job_023 | Quality Assurance Engineer        | QualityFirst Corp (fictional)     | Python, unit testing, Bash, SQL                         | 1.00           |
| job_024 | Cloud-Native Developer            | CloudSoft Inc (fictional)         | Python, AWS, React, SQL                                 | 0.75           |
| job_025 | Data Science Intern               | Insight Analytics (fictional)     | Python, pandas, NumPy, SQL                              | 1.00           |

## Notes

- Scores ≥ 0.25 pass the `NO_MATCH_THRESHOLD` and allow the agent to continue.
- job_003, job_005, job_012 score 0.00 — the agent will stop early with `no_match`.
- job_008, job_010, job_016, job_020 score 0.25 — exactly at the threshold (not below it, so the agent continues).
- job_001, job_019, job_022, job_024 score 0.75 — good fit with one or two skill gaps to address.

## Regenerating postings

```
python -m sandbox.seed
```
