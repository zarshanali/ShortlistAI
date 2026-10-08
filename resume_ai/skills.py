"""Curated skill dictionary for each job category in the Kaggle
'Updated Resume Dataset' (25 categories), plus helpers to find which skills a
resume has and which it is missing (skill-gap analysis).
"""
import re

# category -> list of key skills employers look for
SKILLS_BY_CATEGORY = {
    "Data Science": [
        "python", "r", "machine learning", "deep learning", "statistics",
        "pandas", "numpy", "scikit-learn", "tensorflow", "sql", "data analysis",
        "data visualization", "nlp", "tableau", "power bi", "excel",
    ],
    "Python Developer": [
        "python", "django", "flask", "rest api", "sql", "git", "postgresql",
        "docker", "unit testing", "oop", "linux", "html",
    ],
    "Java Developer": [
        "java", "spring", "spring boot", "hibernate", "sql", "rest api",
        "maven", "git", "junit", "microservices", "javascript", "html",
    ],
    "Web Designing": [
        "html", "css", "javascript", "bootstrap", "photoshop", "figma",
        "responsive design", "ui", "ux", "jquery", "wordpress", "adobe xd",
    ],
    "DotNet Developer": [
        "c#", ".net", "asp.net", "sql server", "mvc", "rest api", "entity framework",
        "azure", "javascript", "git", "linq",
    ],
    "DevOps Engineer": [
        "docker", "kubernetes", "jenkins", "aws", "azure", "terraform", "ansible",
        "linux", "ci cd", "git", "bash", "monitoring",
    ],
    "Network Security Engineer": [
        "network security", "firewall", "cisco", "vpn", "tcp ip", "linux",
        "penetration testing", "ids", "ips", "wireshark", "encryption",
    ],
    "Database": [
        "sql", "mysql", "oracle", "postgresql", "mongodb", "plsql",
        "database design", "indexing", "backup", "etl", "stored procedures",
    ],
    "Hadoop": [
        "hadoop", "hive", "pig", "spark", "mapreduce", "hdfs", "sqoop",
        "kafka", "java", "sql", "big data",
    ],
    "ETL Developer": [
        "etl", "informatica", "sql", "data warehouse", "ssis", "talend",
        "oracle", "data modeling", "python", "unix",
    ],
    "Blockchain": [
        "blockchain", "solidity", "ethereum", "smart contracts", "web3",
        "cryptography", "hyperledger", "bitcoin", "javascript", "node js",
    ],
    "Automation Testing": [
        "selenium", "java", "testng", "automation", "junit", "cucumber",
        "api testing", "jenkins", "git", "python", "test cases",
    ],
    "Testing": [
        "manual testing", "test cases", "selenium", "jira", "bug tracking",
        "regression testing", "sql", "agile", "test plan", "qa",
    ],
    "SAP Developer": [
        "sap", "abap", "sap hana", "sap fico", "sap mm", "sap sd",
        "data dictionary", "smartforms", "idoc", "sql",
    ],
    "Business Analyst": [
        "business analysis", "requirements gathering", "sql", "excel", "agile",
        "scrum", "uml", "jira", "stakeholder management", "documentation",
        "power bi", "data analysis",
    ],
    "Operations Manager": [
        "operations management", "team management", "project management",
        "budgeting", "excel", "supply chain", "process improvement",
        "leadership", "kpi", "scheduling",
    ],
    "PMO": [
        "project management", "pmp", "ms project", "agile", "scrum", "budgeting",
        "risk management", "reporting", "stakeholder management", "excel",
    ],
    "Sales": [
        "sales", "negotiation", "crm", "lead generation", "communication",
        "marketing", "customer relationship", "cold calling", "salesforce",
        "target",
    ],
    "HR": [
        "recruitment", "onboarding", "payroll", "employee relations",
        "performance management", "hr policies", "communication", "excel",
        "talent acquisition", "training",
    ],
    "Advocate": [
        "legal research", "litigation", "drafting", "contract law",
        "case management", "compliance", "negotiation", "legal documentation",
        "court", "client counseling",
    ],
    "Arts": [
        "creativity", "drawing", "painting", "design", "photoshop",
        "illustration", "communication", "adobe", "sketching", "visual arts",
    ],
    "Health and fitness": [
        "fitness training", "nutrition", "anatomy", "exercise", "personal training",
        "physiotherapy", "wellness", "first aid", "communication", "diet planning",
    ],
    "Civil Engineer": [
        "autocad", "civil engineering", "construction", "structural analysis",
        "staad pro", "project management", "surveying", "estimation",
        "concrete", "site management",
    ],
    "Mechanical Engineer": [
        "autocad", "solidworks", "catia", "mechanical design", "ansys",
        "manufacturing", "thermodynamics", "cad", "project management", "gd t",
    ],
    "Electrical Engineering": [
        "circuit design", "matlab", "plc", "power systems", "autocad",
        "electrical machines", "control systems", "scada", "electronics",
        "embedded systems",
    ],
}


def _has_skill(skill, text_lower):
    """Word-boundary match so short skills like 'r' or 'c#' don't false-match."""
    pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
    return re.search(pattern, text_lower) is not None


def match_skills(resume_text, category):
    """Return (matched, missing) skill lists for the given category."""
    skills = SKILLS_BY_CATEGORY.get(category, [])
    text_lower = resume_text.lower()
    matched, missing = [], []
    for skill in skills:
        if _has_skill(skill, text_lower):
            matched.append(skill)
        else:
            missing.append(skill)
    return matched, missing


def all_categories():
    return sorted(SKILLS_BY_CATEGORY.keys())


# =====================================================================
# v2: GLOBAL skill vocabulary - used to read the skills a JOB DESCRIPTION
# asks for (instead of only the fixed per-category lists above).
# =====================================================================
EXTRA_SKILLS = [
    # programming / web
    "c++", "typescript", "react", "angular", "vue", "node js", "express",
    "graphql", "fastapi", "django", "flask", "php", "laravel", "ruby", "golang",
    "rust", "scala", "kotlin", "swift", "android", "ios", "flutter", "matlab",
    "bash", "shell scripting", "data structures", "algorithms", "api development",
    # data / ai
    "pytorch", "keras", "xgboost", "matplotlib", "seaborn", "scipy", "opencv",
    "computer vision", "generative ai", "llm", "langchain", "hugging face",
    "airflow", "dbt", "snowflake", "bigquery", "redshift", "looker", "a/b testing",
    "feature engineering", "time series", "predictive modeling", "mlops",
    # cloud / devops
    "aws", "gcp", "redis", "elasticsearch", "nosql", "firebase", "github",
    "gitlab", "devops", "cloud computing", "serverless", "nginx",
    # business / other
    "agile", "scrum", "jira", "figma", "seo", "digital marketing",
    "google analytics", "content writing", "accounting", "tally", "quickbooks",
    "financial analysis", "market research", "customer service", "recruitment",
    # soft skills
    "leadership", "teamwork", "problem solving", "time management",
    "critical thinking", "presentation", "mentoring",
]

SOFT_SKILLS = {
    "communication", "leadership", "teamwork", "problem solving",
    "time management", "critical thinking", "stakeholder management",
    "negotiation", "creativity", "customer relationship", "team management",
    "presentation", "mentoring",
}

# generic words that appear in the category lists but are too vague to treat
# as a "skill" when reading a job description
_NOISY = {
    "target", "court", "training", "reporting", "documentation", "design",
    "monitoring", "automation", "exercise", "backup", "indexing", "ids", "ips",
    "drawing", "painting",
}

# canonical skill -> other ways people write it
ALIASES = {
    "javascript": ["js", "es6", "ecmascript"],
    "node js": ["node.js", "nodejs", "node"],
    "react": ["reactjs", "react.js"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "machine learning": ["ml"],
    "nlp": ["natural language processing"],
    "deep learning": ["neural networks", "neural network"],
    "ci cd": ["ci/cd", "cicd", "continuous integration", "continuous delivery"],
    "tcp ip": ["tcp/ip"],
    "rest api": ["rest", "restful", "restful api", "rest apis", "restful apis"],
    "power bi": ["powerbi"],
    "postgresql": ["postgres"],
    "kubernetes": ["k8s"],
    "aws": ["amazon web services"],
    "gcp": ["google cloud", "google cloud platform"],
    "azure": ["microsoft azure"],
    "excel": ["microsoft excel", "ms excel"],
    "gd t": ["gd&t"],
    "spring boot": ["springboot"],
    "asp.net": ["aspnet", "asp .net"],
    "sql server": ["mssql", "ms sql", "microsoft sql server"],
    "ms project": ["microsoft project"],
    "data visualization": ["data visualisation", "data viz"],
    "unit testing": ["unit tests"],
    "oop": ["object oriented", "object-oriented", "object oriented programming"],
    "html": ["html5"],
    "css": ["css3"],
    "r": ["r programming", "rstudio", "r language"],   # bare "r" is too ambiguous
    "c#": ["c sharp"],
    "mongodb": ["mongo db"],
    "mysql": ["my sql"],
    "git": ["version control"],
    "problem solving": ["problem-solving"],
    "teamwork": ["team player", "collaboration", "collaborative"],
    "communication": ["communication skills", "verbal communication"],
    "llm": ["large language models", "large language model"],
    "generative ai": ["genai", "gen ai"],
    "computer vision": ["image processing"],
    "ui": ["user interface"],
    "ux": ["user experience"],
    "a/b testing": ["ab testing", "a/b tests"],
    "project management": ["program management"],
    "team management": ["people management", "managing teams"],
    "etl": ["elt"],
}


def _build_vocab():
    vocab = set(EXTRA_SKILLS) | SOFT_SKILLS
    for lst in SKILLS_BY_CATEGORY.values():
        vocab.update(lst)
    vocab -= _NOISY
    return sorted(vocab)


GLOBAL_SKILLS = _build_vocab()


def _compile_patterns():
    pats = {}
    for canon in GLOBAL_SKILLS:
        forms = ALIASES["r"] if canon == "r" else [canon] + ALIASES.get(canon, [])
        forms = sorted({f for f in forms if len(f) > 1}, key=len, reverse=True)
        if forms:
            body = "|".join(re.escape(f) for f in forms)
            pats[canon] = re.compile(r"(?<![a-z0-9])(?:" + body + r")(?![a-z0-9])")
    return pats


_PATTERNS = _compile_patterns()


def extract_skills(text):
    """Return the sorted list of known skills (canonical names) found in text."""
    text_lower = (text or "").lower()
    return sorted(c for c, p in _PATTERNS.items() if p.search(text_lower))


def is_soft(skill):
    return skill in SOFT_SKILLS
