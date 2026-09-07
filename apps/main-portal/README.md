# apps/main-portal - Main Platform Portal

React + Vite, staff-facing only. Beneficiaries do not log in here; staff operate the portal on a beneficiary's behalf.

The portal supports profile entry, eligibility discovery review, outreach pooling, verification, direct applications, ranked candidate cycles, approvals, finalisation records, duplicate review, program rule management, source document storage, a staff source-backed assistant, and a floating public support chatbot for program questions. It keeps marketplace concerns out of this app.

The current UI uses Al-Khidmat's public brand reference and the official logo/font assets in `public/`.

## Run Locally

Start the FastAPI staff API first, then:

```powershell
cd apps/main-portal
..\..\.tools\node.exe ..\..\.tools\package\bin\npm-cli.js install
..\..\.tools\node.exe ..\..\.tools\package\bin\npm-cli.js run dev
```

Open `http://127.0.0.1:5174`. In demo mode, choose `Enter demo workspace`.

The frontend calls `/portal` by default through the Vite proxy. For hosted deployments, set `VITE_STAFF_API_BASE` in `.env`.
