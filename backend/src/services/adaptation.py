from __future__ import annotations


class AdaptationPolicy:
    @staticmethod
    def _detected_language(text: str, profile_language: str) -> str:
        if any("\u0a00" <= char <= "\u0a7f" for char in text): return "punjabi"
        if any("\u0900" <= char <= "\u097f" for char in text): return "hindi"
        if profile_language != "auto": return profile_language
        return "english"

    def resolve(self, *, text: str, profile, language: str | None = None,
                depth: str | None = None, format: str | None = None) -> dict:
        profile_language = profile.preferred_language
        if language and language != "auto": effective_language, language_source = language, "message_override"
        elif language == "auto":
            effective_language, language_source = self._detected_language(text, profile_language), "auto_detection"
        elif profile_language != "auto": effective_language, language_source = profile_language, "profile"
        else: effective_language, language_source = self._detected_language(text, profile_language), "auto_detection"
        return {
            "effective_language": effective_language,
            "effective_depth": depth or profile.preferred_depth or "standard",
            "effective_format": format or profile.preferred_format or "mixed",
            "source": {
                "language": language_source,
                "depth": "message_override" if depth else "profile",
                "format": "message_override" if format else "profile",
            },
        }
