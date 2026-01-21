# Project Setup and Run Commands

Here are the commands and steps required to set up and run the AI Form Filling Assistant project after downloading it from GitHub.

## 1. Prerequisites
Ensure you have the following installed on your system:
- [Docker & Docker Compose](https://www.docker.com/products/docker-desktop)
- [Google Chrome](https://www.google.com/chrome/)
- [Git](https://git-scm.com/downloads)

## 2. Initial Setup
Open your terminal or command prompt in the project root directory.

### Configure Environment Variables
Create the `.env` file from the provided example.

**Windows (PowerShell):**
```powershell
Copy-Item backend/.env.example backend/.env
```

**Linux / macOS (Bash):**
```bash
cp backend/.env.example backend/.env
```

*Optional: Open `backend/.env` in a text editor to customize settings if needed (e.g., database passwords, secret keys).*

## 3. Run the Backend
Build and start the application services using Docker Compose.

```bash
docker-compose up -d --build
```

### Verify Installation
Check if the backend API is running correctly:

```bash
curl http://localhost:8000/health
```
*Expected Output:* `{"status":"healthy",...}`

## 4. Install Chrome Extension
The extension needs to be loaded manually into Chrome:

1. Open Google Chrome.
2. Navigate to `chrome://extensions/` in the address bar.
3. Toggle **Developer mode** to **ON** (top-right corner).
4. Click the **Load unpacked** button (top-left).
5. Select the `chrome-extension` folder located inside this project directory.

## 5. Common Management Commands

**Stop all services:**
```bash
docker-compose down
```

**View backend logs:**
```bash
docker-compose logs -f backend
```

**Restart services:**
```bash
docker-compose restart
```

**Rebuild services (after code changes):**
```bash
docker-compose up -d --build
```

## 6. Quick Start Scripts

Copy and paste these blocks directly into your terminal to start the project.

### Windows (PowerShell)
```powershell
Copy-Item backend/.env.example backend/.env
docker-compose up -d --build
```

### Linux / macOS / Bash
```bash
cp backend/.env.example backend/.env
docker-compose up -d --build
```
