# 🚀 AI-Driven Business Operations & Marketing Intelligence Suite

> **An enterprise AI operations portfolio** integrating real-time Generative AI assistants with automated data pipelines. Built to eliminate manual daily workflows, unlock conversational data insights, and proactively detect brand sentiment and community risks.

**English** | [繁體中文版](README_zh.md)

---

## 📌 Executive Summary

This repository demonstrates the end-to-end implementation of **Generative AI (Gemini 3.7 Flash)** and **Google Cloud Platform (GCP)** architecture in real-world business operations. The solution consists of two complementary systems:

1. **🤖 Multi-Modal WhatsApp AI Operations Assistant (Real-Time)**: An on-demand conversational agent deployed on GCP. Non-technical staff can query databases via natural language, extract data from documents/images, and dispatch CSV/email reports directly within WhatsApp.
2. **📊 Marketing Intelligence & Risk Profiling Pipeline (Automated Batch)**: An autonomous data pipeline running scheduled jobs to clean chat logs, profile community users, analyze brand sentiment, and trigger instant crisis alerts for customer service teams.

---

## 🤖 System 1: Multi-Modal WhatsApp AI Operations Assistant

### 🎥 Live Demo
<!-- Place your GIF file in the assets/ directory -->
![WhatsApp Agent Demo](assets/whatsapp-agent-demo.gif)

### 🏗️ Cloud & Agent Architecture

```mermaid
flowchart TD
    subgraph Client [" 📱 User Interaction Layer"]
        User["User / WhatsApp Group"]
        EvoAPI["Evolution API (WhatsApp Gateway)"]
    end

    subgraph GCP [" ☁️ Google Cloud Platform (Backend Architecture)"]
        PubSub["Google Cloud Pub/Sub\n(Asynchronous Event Decoupling)"]
        CloudFunction["Cloud Functions / Cloud Run\n(Python Agent Core Service)"]
        SecretMgr["Secret Manager\n(Secure Credential Storage)"]
        Firestore["Cloud Firestore\n(Multi-Turn Session Memory & Deduplication)"]
    end

    subgraph AI_Engine [" 🧠 AI & Multi-Modal Engine"]
        Gemini["Google Vertex AI / Gemini 3.7 Flash\n(Tool Calling Loop & Vision Understanding)"]
        DocParser["MarkItDown & Docx Engine\n(Document Text & Embedded Image Extraction)"]
    end

    subgraph External [" 🔌 Data Sources & External Actions"]
        Postgres[("PostgreSQL Database\n(Natural Language Text-to-SQL)")]
        GWorkspace["Google Workspace\n(Drive Search / Sheets Read & Write)"]
        GoogleSearch["Google Web Search\n(Real-Time Web Grounding)"]
        EmailSMTP["Gmail SMTP Service\n(HTML Reports with CSV Attachments)"]
    end

    %% Flow Connections
    User <-->|Text / Image / Document / Command| EvoAPI
    EvoAPI -->|Webhook Event| PubSub
    PubSub -->|Trigger CloudEvent| CloudFunction
    
    CloudFunction <-->|Read / Write Session History| Firestore
    CloudFunction -.->|Retrieve Secrets| SecretMgr
    
    CloudFunction <-->|Prompts & Tool Execution Loop| Gemini
    CloudFunction -->|Parse Attachments| DocParser
    DocParser -->|Multi-Modal Ingestion| Gemini
    
    %% Tool Invocations
    Gemini -->|1. Dynamic Text-to-SQL| Postgres
    Gemini -->|2. Workspace File Ops| GWorkspace
    Gemini -->|3. Live Web Grounding| GoogleSearch
    Gemini -->|4. Automated Email Delivery| EmailSMTP
    
    CloudFunction -->|Return Reply / Send CSV Attachment| EvoAPI
```

### 🧪 Verified Capabilities & Test Scenarios

The system has undergone end-to-end verification across operational workflows:

* **Test 1: Multi-Turn Memory & Session Reset (`/reset`)**
  * **Workflow:** Verified contextual memory across conversations stored in Cloud Firestore.
  * **Result:** Agent recalls contextual user attributes (e.g., user identity) and cleanly wipes history upon issuing `/reset`.
* **Test 2: Natural Language Database Querying (Text-to-SQL)**
  * **Workflow:** Inspects database schemas dynamically and executes safe read-only `SELECT` queries with connection pooling (SQLAlchemy).
  * **Result:** Automatically queries message counts and timestamps, displaying real-time UI feedback (`🔍 Executing SQL...`) before outputting structured insights.
* **Test 3: Big Data Analysis & Physical File Delivery**
  * **Workflow:** Extracts datasets into temporary storage, performs LLM sentiment/categorization analysis, and compiles downloadable reports.
  * **Result:** Delivers real-time progress indicators (`🧠 Analyzing data... ➔ 📊 Packaging report...`) and pushes the physical `.csv` file directly into the WhatsApp chat window.
* **Test 4: Multi-Modal & Document Understanding (Images & Files)**
  * **Workflow:** Evaluates image OCR and multi-format document parsing (`.docx`, `.xlsx`, `.pdf`, `.pptx`).
  * **Result:** Successfully extracts text and embedded flowcharts/screenshots inside documents, combining visual and textual reasoning into concise summaries.
* **Test 5: Automated Email Reporting with Attachments**
  * **Workflow:** Connects with Gmail SMTP to compile formatted HTML reports with data attachments.
  * **Result:** Pushes formatted executive summaries with generated `.csv` files directly to designated stakeholder inboxes.
* **Test 6: Real-Time Web Grounding Search**
  * **Workflow:** Dispatches queries requiring external real-time data (e.g., live exchange rates, financial news) using a dedicated Google Grounding client.
  * **Result:** Accurately summarizes live web data without conflicting with internal tool schemas.
* **Test 7: Group Mention Filtering & Idempotency (Production Guardrail)**
  * **Workflow:** Filters non-relevant group messages and avoids duplicate executions from Pub/Sub retries.
  * **Result:** Agent remains silent unless explicitly `@mentioned` in groups; Firestore-backed deduplication ignores duplicate message IDs.

---

## 📊 System 2: Automated Sentiment & Community Risk Profiling Pipeline

### 🏗️ Pipeline Architecture

```mermaid
flowchart LR
    subgraph Trigger [" ⏱️ Scheduling"]
        Cron["GitHub Actions\n(CRON Job Daily 09:00 HKT)"]
    end

    subgraph Pipeline [" ⚙️ Processing & Risk Scoring Core"]
        DriveIngest["1. Google Drive Ingestion\n(Daily raw chat logs)"]
        CleanDedupe["2. Cleaning & Deduplication\n(Time tolerances & text normalization)"]
        SentimentEngine["3. Gemini LLM Sentiment Engine\n(Positive / Neutral / Negative classification)"]
        RiskEngine["4. 30-Day Behavioral Risk Engine\n(Real / Watch / Business / Seeder scoring)"]
    end

    subgraph Output [" 📊 Dashboard & Alerting"]
        Sheets["Google Sheets Dashboard\n(Batch cell overwriting)"]
        Alert["🚨 CS/PR Urgent Alert\n(Contextual incident payload via Email)"]
    end

    Cron --> DriveIngest
    DriveIngest --> CleanDedupe
    CleanDedupe --> SentimentEngine
    SentimentEngine --> RiskEngine
    RiskEngine --> Sheets
    SentimentEngine -->|Flagged Negative Incident| Alert
```

### 🌟 Key Functional Capabilities

* **🧠 Granular Sentiment & Crisis Alerting:** Scans daily brand discussions and flags urgent negative feedback (attaching chat group, sender phone, timestamp, and quoted messages) to customer service teams.
* **🛡️ 30-Day Historical Risk Profiling:** Tracks cross-group engagement history over 30 days to tag accounts into *Real User*, *Watchlist*, *Commercial Spammer*, or *Competitor Seeder*.
* **📈 Zero-Touch Executive Dashboards:** Automatically aggregates volume, sentiment distribution, and topic trends, updating management dashboards with zero manual intervention.

---

## 💼 Business Impact & Efficiency Gains

| Metric / Dimension | Traditional Manual Workflow | AI-Automated Solution | Impact & Value Added |
| :--- | :--- | :--- | :--- |
| **Daily Data Processing** | 2 – 3 Hours / day | ~15 Minutes / day | **>80% Operational Time Saved** |
| **Data Querying Barrier** | Relies on data/IT team requests | Instant via WhatsApp conversation | **Zero learning curve** for non-technical teams |
| **Crisis Detection** | Discovered passively after complaints | Automated daily morning email alerts | Enables **proactive PR & CS intervention** |
| **Community Quality** | Manual review of spam accounts | Automated 30-day behavior profiling | Protects organic community trust |

---

## 🛠️ Technology Stack

* **AI & Multi-Modal Frameworks:** Google Vertex AI (Gemini Flash), MarkItDown, Python-docx, Prompt Engineering
* **Cloud & Serverless:** Google Cloud Platform (Cloud Functions, Cloud Run, Cloud Pub/Sub, Cloud Secret Manager, Cloud Firestore)
* **Data & Storage:** PostgreSQL, SQLAlchemy (Connection Pooling), Pandas
* **Automation & Gateways:** Evolution API (WhatsApp Gateway), Google Workspace APIs (Sheets & Drive), Gmail SMTP, GitHub Actions

---

## 🔒 Security & Privacy Notice

* **Encrypted Secrets:** All credentials, database URIs, and API tokens are managed via GCP Secret Manager and GitHub Secrets.
* **De-Identified Data:** All demonstration logs, database schemas, and media samples are sanitized for public presentation.
