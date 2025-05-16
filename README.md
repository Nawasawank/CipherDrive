# 🔐 CipherDrive – Secure File Sharing Platform

CipherDrive is a secure file sharing application designed to protect user data using advanced encryption techniques. It enables users to upload, store, and share files with confidence, ensuring privacy and integrity. The system includes tamper detection to alert users when files have been modified.

---

## ✨ Features

- 🔒 **End-to-End Encryption**  
  Combines AES-256 and RSA encryption for maximum security.

- 🛑 **Tamper Detection Alerts**  
  Detects if a file has been altered and notifies the user.

- 👥 **Role-Based Access**  
  Supports multiple user roles: admin, owner, and shared users.

- 📤 **File Sharing via Email**  
  Easily share files securely using recipient email and permission control.

- 📜 **Activity Logging**  
  Tracks access, downloads, and tamper events for auditing purposes.

---

## 🧩 Tech Stack

| Layer      | Technology           |
|------------|----------------------|
| Frontend   | React.js             |
| Backend    | FastAPI (Python)     |
| Storage    | Supabase / Local     |
| Database   | PostgreSQL (via Supabase) |
| Encryption | AES-256, RSA, SHA256 |

---

## 📁 Project Structure

CipherDrive/
├── backend/ # FastAPI backend for file handling, encryption, and user logic
├── frontend/ # React.js frontend for user interaction
└── README.md

---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/Nawasawank/CipherDrive.git
cd CipherDrive

cd backend
pip install -r requirements.txt
uvicorn main:app --reload

cd frontend
npm install
npm start
```
## 🔐 Security Model
- AES-256 for encrypting file contents
- RSA public/private keys for securely sharing AES keys
- SHA256 hashing to verify file integrity and detect tampering
---
