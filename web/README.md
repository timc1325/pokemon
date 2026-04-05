# Pokémon GO Tracker — Next.js + Firebase

Multi-user Pokémon GO collection tracker with Google sign-in.

## Features

- **Google sign-in** — each user gets their own collection
- **Per-user Firestore** — Shundo/Lucky tags stored per account
- **Collection grid** — filter, sort, search, toggle Shundo/Lucky
- **Live Shiny Rates** — fetched from shinyrates.com
- **Dark theme** — matches the original Streamlit design
- **Responsive** — 4 cols mobile, 6 cols tablet, 8 cols desktop

## Firebase Setup

1. Go to [Firebase Console](https://console.firebase.google.com/) → **Create project**
2. **Authentication** → Sign-in method → Enable **Google**
3. **Firestore Database** → Create database (start in production mode)
4. **Firestore Rules** — replace with:
   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       match /users/{userId} {
         allow read, write: if request.auth != null && request.auth.uid == userId;
       }
     }
   }
   ```
5. **Project Settings** → General → Your apps → **Add web app**
6. Copy the config values into `.env.local`:
   ```
   NEXT_PUBLIC_FIREBASE_API_KEY=...
   NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=...
   NEXT_PUBLIC_FIREBASE_PROJECT_ID=...
   NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=...
   NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=...
   NEXT_PUBLIC_FIREBASE_APP_ID=...
   ```

## Local Development

```bash
cd web
npm install
cp .env.local.example .env.local  # fill in your Firebase values
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Deploy to Vercel

1. Push to GitHub
2. Import the repo in [Vercel](https://vercel.com/)
3. Set **Root Directory** to `web`
4. Add all `NEXT_PUBLIC_FIREBASE_*` env vars in Vercel project settings
5. Deploy

## Rollback

The original Streamlit app is still in `app/`. Previous git ref: `3eafa2c`.
