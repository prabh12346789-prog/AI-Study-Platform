from __future__ import annotations


class SubjectTopicClassifier:
    RULES = [
        ("Polity and Governance", "Fundamental Rights", ("article 32", "fundamental right", "right to equality", "writ")),
        ("Polity and Governance", "Constitution", ("constitution", "parliament", "supreme court", "federalism", "governance")),
        ("Economy", "Monetary Policy", ("inflation", "repo rate", "monetary policy", "rbi", "interest rate")),
        ("Economy", "Public Finance", ("budget", "fiscal deficit", "taxation", "gdp")),
        ("Geography", "Climatology", ("monsoon", "cyclone", "climate", "rainfall")),
        ("Geography", "Physical Geography", ("river system", "earthquake", "plate tectonic", "landform")),
        ("Environment and Ecology", "Biodiversity", ("biodiversity", "national park", "wildlife", "ecosystem")),
        ("Environment and Ecology", "Pollution", ("pollution", "air quality", "plastic waste")),
        ("History and Art & Culture", "Modern Indian History", ("quit india", "freedom struggle", "gandhi", "colonial")),
        ("History and Art & Culture", "Ancient and Medieval History", ("mughal", "mauryan", "ashoka", "gupta")),
        ("Science and Technology", "Science and Technology", ("space", "artificial intelligence", "biotechnology", "quantum")),
        ("International Relations", "International Relations", ("united nations", "foreign policy", "bilateral", "geopolitics")),
        ("Ethics", "Ethics and Integrity", ("ethics", "integrity", "probity", "moral dilemma")),
        ("Current Affairs", "Current Affairs", ("current affairs", "recent development", "in the news")),
        ("Essay", "Essay", ("essay",)),
    ]

    def classify(
        self, text: str, *, subject: str | None = None, topic: str | None = None,
    ) -> dict[str, str | float]:
        normalized = " ".join(text.lower().split())
        best = None
        best_matches = 0
        for rule_subject, rule_topic, keywords in self.RULES:
            matches = sum(keyword in normalized for keyword in keywords)
            if matches > best_matches:
                best = (rule_subject, rule_topic)
                best_matches = matches

        if best is None:
            result = {"subject": "General Studies", "topic": "Unclassified", "confidence": 0.25, "method": "keyword_rules"}
        else:
            result = {
                "subject": best[0], "topic": best[1],
                "confidence": min(0.99, 0.86 + (best_matches - 1) * 0.06),
                "method": "keyword_rules",
            }
        if subject is not None or topic is not None:
            result.update({
                "subject": subject or result["subject"],
                "topic": topic or result["topic"],
                "confidence": 1.0,
                "method": "manual_override",
            })
        return result
