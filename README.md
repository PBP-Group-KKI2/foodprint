# FoodPrint
> **Food waste management and reporting system.**

[![PWS Deployment](https://img.shields.io/badge/Deployment-PWS-brightgreen)](https://delitha-theodora-foodprint.pws.cs.ui.ac.id)
[![Figma](https://img.shields.io/badge/Design-Figma-blue)](https://www.figma.com/design/f8Vx2fLgcxBzXWKOyIyuoI/Untitled?node-id=0-1&t=2jf5NFOxM8IgMFHQ-1)

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
*   **Educational Hub:** CRUD on waste categorization guides. Allows admins to post articles and users to filter public API/mock API data on global waste statistics.
*   **Analytics & Dashboards:** CRUD on saved datasets or tracked metrics for environmental organizations. Uses HTMX/AJAX for dynamic chart updates.
*   **Reward System:** CRUD on reward claims and discount coupons. Allows users to redeem points for local restaurant and store vouchers using AJAX for instant balance updates.