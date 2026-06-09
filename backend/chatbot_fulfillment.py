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
    return close(event,
        "My technical skills: "
        "Core languages: C, C++, PHP, Java. "
        "Web: HTML, CSS, JavaScript. "
        "Database: SQL. "
        "Cloud & Security: AWS S3, Lambda, API Gateway, DynamoDB, Cloudflare WAF, IAM. "
        "Languages: Chinese, English, Japanese."
    )

def handle_projects(event):
    return close(event,
        "I have 2 main projects: "
        "1) Cloud Security Serverless Resume System — personal project with Defense in Depth (WAF + S3 Origin Cloaking + API Throttling), DynamoDB Atomic Counter, Amazon Lex v2 Chatbot. GitHub: github.com/Saibusu/MyCloudResume. "
        "2) Gamified Cryptography Learning System — team leader for a cryptography challenge platform (crypto.ttu.taipei), focused on system architecture, API design, and security. Guided by Prof. Huang Kuo-Hsuan."
    )

def handle_education(event):
    return close(event,
        "I study at Tatung University (大同大學), majoring in Computer Science and enrolled in the Information Security program. "
        "I previously attended Yilan Senior High School. "
        "Current class rank: 42nd out of ~141 students (top 29.86%)."
    )

def handle_experience(event):
    return close(event,
        "Teaching: Programming Learning Center TA (2024 both semesters), Programming Lab I & II TA (2026). "
        "Activities: TYPL Engineering Faculty exchange event coordinator, Media Design Department Design Week organizer. "
        "Part-time: College of Engineering administrative office, food service industry."
    )

def handle_contact(event):
    return close(event,
        "You can reach me at: "
        "Email: saibusu8888@gmail.com — "
        "GitHub: github.com/Saibusu — "
        "Phone: 0974-134-535"
    )

def handle_achievements(event):
    return close(event,
        "Certifications: Gemini Certified Educator. "
        "Awards: PUPC 2024 Bronze Award. "
        "Notable experiences: CYBERSEC 2024 Taiwan Cybersecurity Conference, "
        "Team Lab Creative Process Workshop, "
        "Taiwan-Japan Cultural Exchange Design, "
        "AWS Cloud Security Serverless Architecture Implementation."
    )

# ── Helper ────────────────────────────────────────────────────

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
