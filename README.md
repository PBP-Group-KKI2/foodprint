# FoodPrint
> **Food waste management and reporting system.**

[![PWS Deployment](https://img.shields.io/badge/Deployment-PWS-brightgreen)](https://delitha-theodora-foodprint.pws.cs.ui.ac.id)
[![Figma](https://img.shields.io/badge/Design-Figma-blue)](https://www.figma.com/design/YhBHWR2GkBsFA9nxRpUpa3/Design-System-%7C-FoodPrint?m=auto&t=FHjPyd1u4x7syHwU-1)

## Overview
Have you ever walked past overflowing bins and discarded food? You’d think there’s nothing you can do about it and would just leave it to the officials. The problem is, people are not perfect. Officials can be unaware of the existence of that waste. So, how can you help? Well, you have a chance to contribute to the environment through **FoodPrint**!

FoodPrint works as a **food waste reporting system** and **data provider** application. It provides information for citizen users to differentiate the types of food waste and allows them to make reports about the food waste they find in their daily lives. The reports created by them will be stored in a database, and this collection of reports will serve as data for environmental companies, organizations, and local governments to help them take action. 

This application can potentially **raise awareness** for citizens around the world by helping them be more conscious of the food waste around them. It also **provides valuable data** for officials to make their waste management processes more effective.

---

## How to Run Locally

If you want to run this project on your own laptop, follow these steps:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/PBP-Group-KKI2/foodprint.git
   cd foodprint
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Create the environment
   python -m venv env
   
   # Activate on macOS/Linux:
   source env/bin/activate
   # Activate on Windows:
   env\Scripts\activate
   ```

3. **Install the required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Apply database migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Run the development server:**
   ```bash
   python manage.py runserver
   ```
   *Open your browser and navigate to `http://localhost:8000/` to view the app.*

---

## Deployment (PWS)

Set these environment variables on the server. Never commit their values.

| Variable | Purpose |
| :--- | :--- |
| `PRODUCTION` | `True` turns off `DEBUG`, enables secure cookies, and switches to PostgreSQL |
| `SECRET_KEY` | A new random secret (the key in `settings.py` is a public development fallback) |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `SCHEMA` | PostgreSQL connection |

After deploying, run `python manage.py migrate`. Static files are served by WhiteNoise.

---

## Running Tests

```bash
pip install -r requirements-dev.txt                  # adds coverage and selenium
python manage.py test                                # every test, including browser tests (needs Chrome)
python manage.py test --exclude-tag functional       # what CI runs on every push and pull request
coverage run manage.py test educational_hub && coverage report
```

GitHub Actions (`.github/workflows/django.yml`) runs `check`, `makemigrations --check`, and the test suite on every push to `main` and every pull request.

---

### AI Disclosure — Educational Hub and Development Assistance

**Tool:** Claude (Anthropic), including Claude Code in VS Code.

During the development of Foodprint, I used AI as a supporting tool for learning, understanding programming concepts, exploring implementation approaches, and resolving technical problems. As I was still developing my understanding of Django and web development, AI assistance helped me work through unfamiliar concepts and understand how different parts of the application function together.

My use of AI included:

- **Learning and understanding:** Asking for explanations of Django architecture, models, views, URLs, templates, forms, authentication, permissions, and other programming concepts relevant to the project.
- **Implementation planning and guidance:** Discussing possible ways to approach features, identifying which components and files were involved, and breaking unfamiliar implementations into smaller, more understandable steps.
- **Code development:** Using AI suggestions and code assistance when implementing certain features, particularly when working with concepts or functionality that I was not yet familiar with. Claude Code also generated portions of the implementation, which I subsequently reviewed and evaluated against the project's requirements.
- **Debugging and problem-solving:** Using AI to understand error messages, investigate unexpected behavior, and explore possible solutions when testing the application.
- **Code review and refinement:** Discussing potential improvements, identifying edge cases, and reviewing alternative implementations. I made decisions about which suggestions suited the project, including modifying or reverting changes when necessary.

Throughout development, I remained involved in deciding how features should behave, evaluating suggested approaches, checking implementations, and making adjustments based on the project's requirements. AI assistance was used to support my development process and understanding of the codebase, rather than as a substitute for understanding the implementation.

### AI Disclosure — Reporting & Mapping and Development/Bug Fixing Assistance 
I used Claude (Anthropic) as a coding assistant during this project.

How I used it:
- Generating code drafts for parts of my Reporting & Mapping module (views, forms,
  templates, map JavaScript)
- Explaining Django concepts, helping with debugging errors (migration conflicts, CSRF,
  template errors), and walking me through Git workflows (branching, merging,
  resolving conflicts)
- Reviewing branches for merge conflicts and test failures

What I did myself:
- Decided the features and behaviour (Who can access what section, who can edit etc)
- Wrote/changed parts myself: (the Analytics role-based nav visibility, routing for urls in my module, view and models of reporting and mapping too)
- Reviewed, adapted and integrated all AI-generated code into the project
- Tested every feature manually and with the test suite before each PR
- Resolved merge conflicts, opened and merged PRs, and coordinated changes with
  teammates

During development process, I still looked over what the AI tried to add / alter and made sure it followed my intentions with the module itself. I used the AI as a support to speed up development

### Other modules
- **Analytics & Dashboards (Muhammad Arsyad Avmeilputra):** _to be completed_
- **Profile (Dihya Fauzan Haryadi):** _to be completed_
- **Reward System (Kenaz Shidqi Baswara):** _to be completed_
- **Task Dispatch System (Sorush Baghertash):** _to be completed_

---

## Project Details

### What?
Food waste is a form of trash that can be degraded by nature in a relatively short time. These forms of trash are the most common in the world, mostly taking the form of food scraps, rotten fruit, meat, etc. 

Food waste management is a way to minimize this waste from getting into landfills, which could possibly create a breeding ground for diseases and many other health-related issues.

The application works as a **food waste reporting system** and **data provider**. It provides information for users to differentiate the types of food waste, make reports regarding waste findings, and provides food waste data from all of the gathered reports.

### Why?
The application can potentially **raise awareness** for people around the world and create a forum where people can report this specific waste so it can potentially be handled by the local government or by a waste management company.

### How?
The application **provides information** to users regarding waste types or categories. Users are then able to **create a report** when locating waste in their area by providing the location, the waste type/category, etc. The **reports** from various users will be stored in the **application’s database.**

### Who?
This app is designed for various roles within the ecosystem:
*   **Citizens / Community Reporters:** To gain information regarding food waste and allow them to contribute to waste management by informing officials of waste locations.
*   **Waste Management Officials & Local Government:** To access waste data, allowing them to take targeted action.
*   **Environment Awareness Organizations:** To utilize data for campaigns and sustainability efforts.
*   **System Administrators:** To manage and maintain the platform.

### When?
Hopefully, if this ambitious project goes well, it should be ready and open to the public on **October 23rd, 2026**, aligning with the deadline for this group assignment.

---

## Tech Stack & API Integration
*   **Mapping & Location Services:** [OpenStreetMap](https://www.openstreetmap.org/) (Used for documenting and pinpointing waste report locations).
*   **Global Food Waste Data:** [Our World in Data — Food waste per capita](https://ourworldindata.org/grapher/food-waste-per-capita) (FAO/UNEP, SDG 12.3.1). Fetched on the server, cached for 12 hours, and served from the last good copy if the source is down.

---

## The Team & Modules

| Name | Student ID | Assigned Module |
| :--- | :--- | :--- |
| **Muhammad Arsyad Avmeilputra** | 2506556246 | Analytics & Dashboards |
| **Dihya Fauzan Haryadi** | 2506637003 | Profile |
| **Kenaz Shidqi Baswara** | 2506558144 | Reward System |
| **Delitha Theodora** | 2506553585 | Educational Hub |
| **Goran Adriano Tamrella** | 2506558251 | Reporting & Mapping |
| **Sorush Baghertash** | 2606816434 | Task Dispatch System |

### Module Details
*   **Reporting & Mapping:** CRUD on waste reports. Integrates the OpenStreetMap API to pin waste locations. Uses AJAX to submit reports without reloading the map.
*   **Profile:** CRUD on user profiles. Handles authentication-based filtering to ensure officials, citizens, and organizations see appropriate dashboards.
*   **Task Dispatch System:** CRUD on collection tasks. Allows waste management officials to claim, update, and close pending reports.
*   **Educational Hub:** CRUD on articles about sorting and reducing food waste, with likes, saves, and comments (HTMX). Anyone can search and filter articles by topic and browse public global food waste data by country, region, and year.
*   **Analytics & Dashboards:** CRUD on saved datasets or tracked metrics for environmental organizations. Uses HTMX/AJAX for dynamic chart updates.
*   **Reward System:** CRUD on reward claims and discount coupons. Allows users to redeem points for local restaurant and store vouchers using AJAX for instant balance updates.
