import json
import urllib.request

VISITOR_API_URL = "https://3ai7u70ypd.execute-api.us-east-1.amazonaws.com/prod/visitor"

def lambda_handler(event, context):
    intent_name = event["sessionState"]["intent"]["name"]

    handlers = {
        "GetVisitorCount": handle_visitor_count,
        "AskAboutMe":      handle_about_me,
        "AskSkills":       handle_skills,
        "AskProjects":     handle_projects,
        "AskEducation":    handle_education,
        "AskExperience":   handle_experience,
        "AskContact":      handle_contact,
        "AskAchievements": handle_achievements,
        "FallbackIntent":  handle_fallback,
    }

    handler = handlers.get(intent_name)
    if handler:
        return handler(event)
    return respond(event, "Sorry, I didn't understand. Try: skills, projects, education, experience, contact, or achievements.")

# ── Non-slot Handlers ──────────────────────────────────────────

def handle_visitor_count(event):
    try:
        req = urllib.request.Request(VISITOR_API_URL, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            count = data.get("count", "unknown")
        msg = f"This website has been visited {count} times!"
    except Exception:
        msg = "Visitor count is temporarily unavailable, please try again later."
    return respond(event, msg)

def handle_about_me(event):
    return respond(event,
        "I'm Lee Hsuan-Chieh (李軒杰), a Computer Science student at Tatung University, "
        "specializing in cloud architecture and information security. "
        "I built this resume site with AWS S3, Lambda, API Gateway, and Cloudflare WAF. "
        "GitHub: github.com/Saibusu"
    )

def handle_contact(event):
    return respond(event,
        "You can reach me at: "
        "Email: saibusu8888@gmail.com — "
        "GitHub: github.com/Saibusu — "
        "Phone: 0974-134-535"
    )

# ── Slot-based Handlers ────────────────────────────────────────

def handle_skills(event):
    t = _transcript(event)
    skill_type = _slot_value(event, "skillType") or _match_skill(t)
    if skill_type:
        return respond(event, _skills_text(skill_type))
    return ask_pending(event, "skillType", "skills",
        "Which type of skills? (programming / cloud / spoken languages)")

def handle_projects(event):
    t = _transcript(event)
    project_type = _slot_value(event, "projectType") or _match_project(t)
    if project_type:
        return respond(event, _projects_text(project_type))
    return ask_pending(event, "projectType", "projects",
        "Which project? (resume site / cryptography system)")

def handle_education(event):
    t = _transcript(event)
    edu_type = _slot_value(event, "educationType") or _match_education(t)
    if edu_type:
        return respond(event, _education_text(edu_type))
    return ask_pending(event, "educationType", "education",
        "Which education? (university / high school)")

def handle_experience(event):
    t = _transcript(event)
    exp_type = _slot_value(event, "experienceType") or _match_experience(t)
    if exp_type:
        return respond(event, _experience_text(exp_type))
    return ask_pending(event, "experienceType", "experience",
        "Which experience? (teaching / activities / part-time)")

def handle_achievements(event):
    t = _transcript(event)
    ach_type = _slot_value(event, "achievementType") or _match_achievement(t)
    if ach_type:
        return respond(event, _achievements_text(ach_type))
    return ask_pending(event, "achievementType", "achievements",
        "Which achievements? (awards / certificates / events)")

# ── Fallback Handler (catches slot answers Lex can't match) ────

def handle_fallback(event):
    pending = _session_attrs(event).get("pending", "")
    t = _transcript(event)

    if pending == "skills":
        return respond(event, _skills_text(_match_skill(t) or "all"))
    if pending == "projects":
        return respond(event, _projects_text(_match_project(t) or "all"))
    if pending == "education":
        return respond(event, _education_text(_match_education(t) or "all"))
    if pending == "experience":
        return respond(event, _experience_text(_match_experience(t) or "all"))
    if pending == "achievements":
        return respond(event, _achievements_text(_match_achievement(t) or "all"))

    return respond(event,
        "Sorry, I didn't understand. Try asking about: "
        "skills, projects, education, experience, contact, or achievements."
    )

# ── Content ────────────────────────────────────────────────────

def _skills_text(t):
    if t == "programming":
        return ("Programming skills: Core languages: C, C++, PHP, Java. "
                "Web: HTML, CSS, JavaScript. Database: SQL.")
    if t == "cloud":
        return ("Cloud & DevOps skills: AWS S3, Lambda, API Gateway, DynamoDB, Lex v2, IAM, "
                "Cloudflare WAF, GitHub Actions CI/CD, Prisma ORM, NeonDB PostgreSQL.")
    if t in ("spoken", "language", "languages"):
        return "Spoken languages: Chinese (native), English (proficient), Japanese (basic)."
    return ("Skills: Programming (C, C++, PHP, Java, JS, SQL), "
            "Cloud (AWS, Cloudflare WAF, CI/CD), "
            "Spoken languages (Chinese, English, Japanese).")

def _projects_text(t):
    if t == "resume":
        return ("Cloud Security Serverless Resume System: "
                "Defense in Depth architecture (WAF + S3 Origin Cloaking + API Throttling), "
                "DynamoDB Atomic Counter, Amazon Lex v2 Chatbot, NeonDB + Prisma ORM. "
                "GitHub: github.com/Saibusu/MyCloudResume")
    if t == "cryptography":
        return ("Gamified Cryptography Learning System: "
                "Team leader responsible for system architecture, API design, and backend. "
                "Live at: crypto.ttu.taipei (2024-2025). "
                "Guided by Prof. Huang Kuo-Hsuan.")
    return ("I have 2 projects: 1) Cloud Resume (github.com/Saibusu/MyCloudResume) "
            "2) Cryptography Platform (crypto.ttu.taipei). Ask me about one specifically!")

def _education_text(t):
    if t == "university":
        return ("Tatung University (大同大學): "
                "Major in Computer Science and Engineering, "
                "enrolled in the Information Security program. "
                "Class rank: 42nd out of ~141 students (top 29.86%).")
    if t in ("high school", "highschool", "yilan", "high"):
        return ("Yi-Lan Senior High School (宜蘭高中): "
                "Completed high school before entering Tatung University.")
    return ("Education: Tatung University (Computer Science + Information Security). "
            "Previously: Yi-Lan Senior High School. Class rank: 42nd / ~141 (top 29.86%).")

def _experience_text(t):
    if t == "teaching":
        return ("Teaching experience: "
                "Programming Learning Center TA (2024, both semesters), "
                "Programming Lab I & II TA (2026).")
    if t == "activities":
        return ("Activities & events: "
                "TYPL Engineering Faculty Exchange event coordinator, "
                "Media Design Department Design Week organizer.")
    if t in ("part-time", "part time", "job", "work", "part"):
        return ("Part-time work: "
                "College of Engineering administrative office, "
                "food service industry.")
    return ("Experience: Teaching TA (2024-2026), "
            "Events coordinator (TYPL, Design Week), "
            "Part-time at College of Engineering admin office.")

def _achievements_text(t):
    if t == "awards":
        return "Awards: PUPC 2024 Bronze Award."
    if t in ("certificates", "certificate"):
        return ("Certifications: Gemini Certified Educator, "
                "AWS Cloud Security Serverless Architecture Implementation.")
    if t in ("events", "event"):
        return ("Notable events attended: "
                "CYBERSEC 2024 Taiwan Cybersecurity Conference, "
                "Team Lab Creative Process Workshop, "
                "Taiwan-Japan Cultural Exchange Design.")
    return ("Achievements: Awards: PUPC 2024 Bronze Award. "
            "Certifications: Gemini Certified Educator. "
            "Events: CYBERSEC 2024, Team Lab Workshop, Taiwan-Japan Cultural Exchange.")

# ── Matchers ───────────────────────────────────────────────────

def _match_skill(t):
    if any(w in t for w in ["programming", "coding", "code", "tech stack", "java", "python", "php", "c++"]):
        return "programming"
    if any(w in t for w in ["cloud", "aws", "devops", "infrastructure", "lambda", "s3"]):
        return "cloud"
    if any(w in t for w in ["spoken", "language", "languages", "speak", "chinese", "english", "japanese"]):
        return "spoken"
    return None

def _match_project(t):
    if any(w in t for w in ["resume", "serverless", "saibusu", "mycloudresume", "first", "1"]):
        return "resume"
    if any(w in t for w in ["cryptography", "crypto", "ttu", "second", "cipher", "2"]):
        return "cryptography"
    return None

def _match_education(t):
    if any(w in t for w in ["university", "tatung", "college", "uni", "degree"]):
        return "university"
    if any(w in t for w in ["high school", "highschool", "yilan", "secondary", "high"]):
        return "high school"
    return None

def _match_experience(t):
    if any(w in t for w in ["teaching", "ta", "teacher", "lab", "assistant"]):
        return "teaching"
    if any(w in t for w in ["activities", "activity", "coordinator", "organizer", "club"]):
        return "activities"
    if any(w in t for w in ["part", "job", "work", "part-time", "parttime"]):
        return "part-time"
    return None

def _match_achievement(t):
    if any(w in t for w in ["award", "awards", "prize", "pupc", "bronze", "competition", "won"]):
        return "awards"
    if any(w in t for w in ["certificate", "certificates", "certification", "gemini", "certified"]):
        return "certificates"
    if any(w in t for w in ["event", "events", "conference", "cybersec", "workshop", "attended"]):
        return "events"
    return None

# ── Helpers ────────────────────────────────────────────────────

def ask_pending(event, slot_name, topic, message):
    """Ask a sub-question and record the pending topic in session."""
    attrs = {**_session_attrs(event), "pending": topic}
    return {
        "sessionState": {
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": slot_name},
            "intent": event["sessionState"]["intent"],
            "sessionAttributes": attrs
        },
        "messages": [{"contentType": "PlainText", "content": message}]
    }

def respond(event, message):
    """Close the turn and clear pending state."""
    attrs = {k: v for k, v in _session_attrs(event).items() if k != "pending"}
    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {
                "name": event["sessionState"]["intent"]["name"],
                "state": "Fulfilled"
            },
            "sessionAttributes": attrs
        },
        "messages": [{"contentType": "PlainText", "content": message}]
    }

def _slot_value(event, slot_name):
    slots = event["sessionState"]["intent"].get("slots", {})
    slot = slots.get(slot_name)
    if slot and slot.get("value"):
        return slot["value"]["interpretedValue"].lower()
    return None

def _transcript(event):
    return event.get("inputTranscript", "").lower()

def _session_attrs(event):
    return event.get("sessionState", {}).get("sessionAttributes") or {}
