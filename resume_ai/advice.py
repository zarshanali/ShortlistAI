"""Turn the raw numbers into plain-language next steps for the job seeker."""


def build_advice(profile, ats, match=None):
    tips = []
    if match:
        s = match["score"]
        if match["missing_required"]:
            top = ", ".join(match["missing_required"][:6])
            tips.append(
                f"The job asks for {top}, which your resume does not mention. If you really "
                "have this experience, add it to your Skills section and name a project or job "
                "where you used it. If you don't, treat it as your learning list - don't add "
                "skills you can't back up in an interview.")
        if match["years_need"] and match["years_have"] < match["years_need"]:
            tips.append(
                f"The role asks for about {match['years_need']:g} years of experience and we "
                f"found {match['years_have']:g}. Make internships, freelance work and serious "
                "projects visible, with dates, so they count.")
        if match["missing_keywords"]:
            tips.append("Words this job uses often but your resume doesn't: "
                        + ", ".join(match["missing_keywords"][:8])
                        + ". Use the ones that honestly describe your work.")
        if s >= 75:
            tips.append("Strong match - apply. Put the matching skills near the top of the resume.")
        elif s < 35:
            tips.append("This role may be a stretch right now. Look at roles closer to your "
                        "current skills (see 'Best-fit roles'), or build the missing skills first.")
    failed = [c for c in ats["checks"] if c["status"] != "pass"]
    failed.sort(key=lambda c: c["max"] - c["points"], reverse=True)
    for c in failed[:4]:
        tips.append(c["tip"])
    if profile["word_count"] < 100:
        tips.insert(0, "Very little text was read from this file. If it is a scanned/image PDF, "
                       "export a text-based PDF or DOCX instead.")
    return tips
