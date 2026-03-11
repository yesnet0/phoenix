"""Skill inference engine — maps researchers to canonical skill categories.

Three-pass inference:
  Pass 1: Explicit skill_tags from profile data (Intigriti etc.)
  Pass 2: Platform specialization heuristics
  Pass 3: Bio text keyword matching
"""

from neo4j import AsyncSession

from phoenix.core.logging import get_logger

log = get_logger(__name__)

# The 9 PRD skill categories
SKILL_CATEGORIES = [
    "Web Application Security",
    "Mobile Security",
    "API Security",
    "Network/Infrastructure",
    "Cloud Security",
    "Smart Contract/Blockchain",
    "IoT/Hardware",
    "Cryptography",
    "Source Code Review",
]

# Pass 1: Map explicit skill_tags keywords to canonical categories
TAG_TO_SKILL: dict[str, str] = {
    # Web
    "web": "Web Application Security",
    "xss": "Web Application Security",
    "sqli": "Web Application Security",
    "sql injection": "Web Application Security",
    "csrf": "Web Application Security",
    "ssrf": "Web Application Security",
    "idor": "Web Application Security",
    "web application": "Web Application Security",
    "webapp": "Web Application Security",
    "owasp": "Web Application Security",
    "rce": "Web Application Security",
    "lfi": "Web Application Security",
    "rfi": "Web Application Security",
    "xxe": "Web Application Security",
    # Mobile
    "mobile": "Mobile Security",
    "android": "Mobile Security",
    "ios": "Mobile Security",
    "mobile application": "Mobile Security",
    "apk": "Mobile Security",
    # API
    "api": "API Security",
    "rest": "API Security",
    "graphql": "API Security",
    "api security": "API Security",
    # Network
    "network": "Network/Infrastructure",
    "infrastructure": "Network/Infrastructure",
    "pentest": "Network/Infrastructure",
    "penetration testing": "Network/Infrastructure",
    "nmap": "Network/Infrastructure",
    "firewall": "Network/Infrastructure",
    # Cloud
    "cloud": "Cloud Security",
    "aws": "Cloud Security",
    "azure": "Cloud Security",
    "gcp": "Cloud Security",
    "kubernetes": "Cloud Security",
    "docker": "Cloud Security",
    "s3": "Cloud Security",
    "iam": "Cloud Security",
    # Smart Contract
    "smart contract": "Smart Contract/Blockchain",
    "blockchain": "Smart Contract/Blockchain",
    "solidity": "Smart Contract/Blockchain",
    "web3": "Smart Contract/Blockchain",
    "defi": "Smart Contract/Blockchain",
    "ethereum": "Smart Contract/Blockchain",
    "evm": "Smart Contract/Blockchain",
    "vyper": "Smart Contract/Blockchain",
    "rust": "Smart Contract/Blockchain",
    # IoT
    "iot": "IoT/Hardware",
    "hardware": "IoT/Hardware",
    "embedded": "IoT/Hardware",
    "firmware": "IoT/Hardware",
    # Crypto
    "cryptography": "Cryptography",
    "crypto": "Cryptography",
    "encryption": "Cryptography",
    "tls": "Cryptography",
    "ssl": "Cryptography",
    "pki": "Cryptography",
    # Source Code
    "source code": "Source Code Review",
    "code review": "Source Code Review",
    "sast": "Source Code Review",
    "static analysis": "Source Code Review",
    "code audit": "Source Code Review",
}

# Pass 2: Platform → skill heuristics
PLATFORM_SKILLS: dict[str, list[str]] = {
    "code4rena": ["Smart Contract/Blockchain"],
    "sherlock": ["Smart Contract/Blockchain"],
    "immunefi": ["Smart Contract/Blockchain"],
    "codehawks": ["Smart Contract/Blockchain"],
    "hatsfinance": ["Smart Contract/Blockchain"],
    "cantina": ["Smart Contract/Blockchain"],
    "patchstack": ["Web Application Security", "Source Code Review"],
    "huntr": ["Source Code Review", "Web Application Security"],
    "hackenproof": ["Smart Contract/Blockchain", "Web Application Security"],
}

# Pass 3: Bio keywords → skills (checked as substrings)
BIO_KEYWORDS: dict[str, str] = {
    "smart contract": "Smart Contract/Blockchain",
    "blockchain": "Smart Contract/Blockchain",
    "solidity": "Smart Contract/Blockchain",
    "web3": "Smart Contract/Blockchain",
    "defi": "Smart Contract/Blockchain",
    "ethereum": "Smart Contract/Blockchain",
    "mobile": "Mobile Security",
    "android": "Mobile Security",
    "ios security": "Mobile Security",
    "api": "API Security",
    "cloud": "Cloud Security",
    "aws": "Cloud Security",
    "azure": "Cloud Security",
    "kubernetes": "Cloud Security",
    "iot": "IoT/Hardware",
    "hardware": "IoT/Hardware",
    "embedded": "IoT/Hardware",
    "firmware": "IoT/Hardware",
    "cryptography": "Cryptography",
    "encryption": "Cryptography",
    "code review": "Source Code Review",
    "source code": "Source Code Review",
    "static analysis": "Source Code Review",
    "pentest": "Network/Infrastructure",
    "penetration test": "Network/Infrastructure",
    "network": "Network/Infrastructure",
    "infrastructure": "Network/Infrastructure",
    "web application": "Web Application Security",
    "xss": "Web Application Security",
    "sqli": "Web Application Security",
    "owasp": "Web Application Security",
    "bug bounty": "Web Application Security",
}


async def _pass1_explicit_tags(session: AsyncSession) -> int:
    """Map existing skill_tags from profiles to canonical Skill nodes."""
    result = await session.run(
        """
        MATCH (p:PlatformProfile)
        WHERE p.skill_tags IS NOT NULL AND size(p.skill_tags) > 0
        RETURN p.id AS id, p.skill_tags AS tags
        """
    )
    created = 0
    async for record in result:
        profile_id = record["id"]
        tags = record["tags"]
        matched_skills: set[str] = set()
        for tag in tags:
            tag_lower = tag.lower().strip()
            for keyword, skill in TAG_TO_SKILL.items():
                if keyword in tag_lower:
                    matched_skills.add(skill)
        for skill in matched_skills:
            await session.run(
                """
                MATCH (p:PlatformProfile {id: $profile_id})
                MATCH (s:Skill {name: $skill_name})
                MERGE (p)-[r:HAS_SKILL]->(s)
                ON CREATE SET r.source = 'explicit'
                """,
                profile_id=profile_id,
                skill_name=skill,
            )
            created += 1
    return created


async def _pass2_platform_heuristics(session: AsyncSession) -> int:
    """Infer skills from platform specialization."""
    created = 0
    for platform_name, skills in PLATFORM_SKILLS.items():
        for skill_name in skills:
            res = await session.run(
                """
                MATCH (p:PlatformProfile {platform_name: $platform_name})
                MATCH (s:Skill {name: $skill_name})
                WHERE NOT (p)-[:HAS_SKILL]->(s)
                MERGE (p)-[r:HAS_SKILL]->(s)
                ON CREATE SET r.source = 'platform'
                RETURN count(r) AS created
                """,
                platform_name=platform_name,
                skill_name=skill_name,
            )
            rec = await res.single()
            created += rec["created"] if rec else 0
    return created


async def _pass3_bio_keywords(session: AsyncSession) -> int:
    """Scan bio text for skill keywords."""
    result = await session.run(
        """
        MATCH (p:PlatformProfile)
        WHERE p.bio IS NOT NULL AND p.bio <> ''
        RETURN p.id AS id, p.bio AS bio
        """
    )
    created = 0
    async for record in result:
        profile_id = record["id"]
        bio_lower = record["bio"].lower()
        matched_skills: set[str] = set()
        for keyword, skill in BIO_KEYWORDS.items():
            if keyword in bio_lower:
                matched_skills.add(skill)
        for skill in matched_skills:
            await session.run(
                """
                MATCH (p:PlatformProfile {id: $profile_id})
                MATCH (s:Skill {name: $skill_name})
                MERGE (p)-[r:HAS_SKILL]->(s)
                ON CREATE SET r.source = 'bio'
                """,
                profile_id=profile_id,
                skill_name=skill,
            )
            created += 1
    return created


async def run_skill_inference(session: AsyncSession) -> dict:
    """Run the full 3-pass skill inference pipeline.

    Returns dict with counts from each pass.
    """
    pass1 = await _pass1_explicit_tags(session)
    await log.ainfo("skill_inference_pass1", edges_created=pass1)

    pass2 = await _pass2_platform_heuristics(session)
    await log.ainfo("skill_inference_pass2", edges_created=pass2)

    pass3 = await _pass3_bio_keywords(session)
    await log.ainfo("skill_inference_pass3", edges_created=pass3)

    total_result = await session.run(
        "MATCH ()-[r:HAS_SKILL]->() RETURN count(r) AS total"
    )
    total_rec = await total_result.single()
    total = total_rec["total"] if total_rec else 0

    return {
        "pass1_explicit": pass1,
        "pass2_platform": pass2,
        "pass3_bio": pass3,
        "total_edges": total,
    }
