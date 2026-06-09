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
    }

    handler = handlers.get(intent_name)
    if handler:
        return handler(event)
    return close(event, "Sorry, I didn't understand. Try asking: skills, projects, education, experience, contact, or achievements.")

# ── Intent Handlers ──────────────────────────────────────────

def handle_visitor_count(event):
    try:
        req = urllib.request.Request(VISITOR_API_URL, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            count = data.get("count", "unknown")
        message = f"This website has been visited {count} times!"
    except Exception:
        message = "Visitor count is temporarily unavailable, please try again later."
    return close(event, message)

def handle_about_me(event):
    return close(event,
        "I'm Lee Hsuan-Chieh (李軒杰), a Computer Science student at Tatung University, "
        "specializing in cloud architecture and information security. "
        "I built this resume site with AWS S3, Lambda, API Gateway, and Cloudflare WAF. "
        "GitHub: github.com/Saibusu"
    )

def handle_skills(event):
    slots = event["sessionState"]["intent"].get("slots", {})
    skill_slot = slots.get("skillType")

    if skill_slot and skill_slot.get("value"):
        skill_type = skill_slot["value"]["interpretedValue"].lower()

        if skill_type == "programming":
            return close(event,
                "Programming skills: "
                "Core languages: C, C++, PHP, Java. "
                "Web: HTML, CSS, JavaScript. "
                "Database: SQL."
            )
        elif skill_type == "cloud":
            return close(event,
                "Cloud & DevOps skills: "
                "AWS S3, Lambda, API Gateway, DynamoDB, Lex v2, IAM, "
                "Cloudflare WAF, GitHub Actions CI/CD, Prisma ORM, NeonDB PostgreSQL."
            )
        elif skill_type in ("spoken", "language", "languages"):
            return close(event,
                "Spoken languages: "
                "Chinese (native), English (proficient), Japanese (basic)."
            )
        else:
            return close(event,
                "Skills: Programming (C, C++, PHP, Java, JS, SQL), "
                "Cloud (AWS, Cloudflare WAF, CI/CD), "
                "Spoken languages (Chinese, English, Japanese)."
            )

    # Slot not yet filled — delegate back to Lex to elicit the slot
    return delegate(event)

def handle_projects(event):
    slots = event["sessionState"]["intent"].get("slots", {})
    project_slot = slots.get("projectType")

    if project_slot and project_slot.get("value"):
        project_type = project_slot["value"]["interpretedValue"].lower()

        if project_type == "resume":
            return close(event,
                "Cloud Security Serverless Resume System: "
                "Defense in Depth architecture (WAF + S3 Origin Cloaking + API Throttling), "
                "DynamoDB Atomic Counter, Amazon Lex v2 Chatbot, NeonDB + Prisma ORM. "
                "GitHub: github.com/Saibusu/MyCloudResume"
            )
        elif project_type == "cryptography":
            return close(event,
                "Gamified Cryptography Learning System: "
                "Team leader responsible for system architecture, API design, and backend. "
                "Live at: crypto.ttu.taipei (2024-2025). "
                "Guided by Prof. Huang Kuo-Hsuan."
            )
        else:
            return close(event,
                "I have 2 projects: 1) Cloud Resume (github.com/Saibusu/MyCloudResume) "
                "2) Cryptography Platform (crypto.ttu.taipei). Ask me about one specifically!"
            )

    return delegate(event)

def handle_education(event):
    slots = event["sessionState"]["intent"].get("slots", {})
    edu_slot = slots.get("educationType")

    if edu_slot and edu_slot.get("value"):
        edu_type = edu_slot["value"]["interpretedValue"].lower()

        if edu_type == "university":
            return close(event,
                "Tatung University (大同大學): "
                "Major in Computer Science and Engineering, "
                "enrolled in the Information Security program. "
                "Class rank: 42nd out of ~141 students (top 29.86%)."
            )
        elif edu_type in ("high school", "highschool", "yilan"):
            return close(event,
                "Yi-Lan Senior High School (宜蘭高中): "
                "Completed high school before entering Tatung University."
            )
        else:
            return close(event,
                "Education: Tatung University (Computer Science + Information Security). "
                "Previously: Yi-Lan Senior High School. Class rank: 42nd / ~141 (top 29.86%)."
            )

    return delegate(event)

def handle_experience(event):
    slots = event["sessionState"]["intent"].get("slots", {})
    exp_slot = slots.get("experienceType")

    if exp_slot and exp_slot.get("value"):
        exp_type = exp_slot["value"]["interpretedValue"].lower()

        if exp_type == "teaching":
            return close(event,
                "Teaching experience: "
                "Programming Learning Center TA (2024, both semesters), "
                "Programming Lab I & II TA (2026)."
            )
        elif exp_type == "activities":
            return close(event,
                "Activities & events: "
                "TYPL Engineering Faculty Exchange event coordinator, "
                "Media Design Department Design Week organizer."
            )
        elif exp_type in ("part-time", "part time", "job", "work"):
            return close(event,
                "Part-time work: "
                "College of Engineering administrative office, "
                "food service industry."
            )
        else:
            return close(event,
                "Experience: Teaching TA (2024-2026), "
                "Events coordinator (TYPL, Design Week), "
                "Part-time at College of Engineering admin office."
            )

    return delegate(event)

def handle_contact(event):
    return close(event,
        "You can reach me at: "
        "Email: saibusu8888@gmail.com — "
        "GitHub: github.com/Saibusu — "
        "Phone: 0974-134-535"
    )

def handle_achievements(event):
    slots = event["sessionState"]["intent"].get("slots", {})
    ach_slot = slots.get("achievementType")

    if ach_slot and ach_slot.get("value"):
        ach_type = ach_slot["value"]["interpretedValue"].lower()

        if ach_type == "awards":
            return close(event,
                "Awards: PUPC 2024 Bronze Award."
            )
        elif ach_type in ("certificates", "certificate"):
            return close(event,
                "Certifications: Gemini Certified Educator, "
                "AWS Cloud Security Serverless Architecture Implementation."
            )
        elif ach_type in ("events", "event"):
            return close(event,
                "Notable events attended: "
                "CYBERSEC 2024 Taiwan Cybersecurity Conference, "
                "Team Lab Creative Process Workshop, "
                "Taiwan-Japan Cultural Exchange Design."
            )
        else:
            return close(event,
                "Achievements: "
                "Awards: PUPC 2024 Bronze Award. "
                "Certifications: Gemini Certified Educator. "
                "Events: CYBERSEC 2024, Team Lab Workshop, Taiwan-Japan Cultural Exchange."
            )

    return delegate(event)

# ── Helpers ───────────────────────────────────────────────────

def delegate(event):
    return {
        "sessionState": {
            "dialogAction": {"type": "Delegate"},
            "intent": event["sessionState"]["intent"]
        }
    }

def close(event, message):
    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {
                "name": event["sessionState"]["intent"]["name"],
                "state": "Fulfilled"
            }
        },
        "messages": [{"contentType": "PlainText", "content": message}]
    }
