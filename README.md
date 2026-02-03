# Shoe Matcher

AI-powered shoe recommendation platform that matches users to their ideal running or basketball shoes based on a quiz, foot profile, and AI-enriched shoe data aggregated from reviews.

## Features

- **60-second Quiz**: Answer questions about your feet, preferences, and use case
- **AI-Powered Matching**: Algorithm scores shoes against your profile using weighted criteria
- **Review Intelligence**: AI-parsed reviews extract fit data like sizing, width, and durability
- **Unbiased Recommendations**: Not tied to any retailer - compare prices across multiple sources
- **Admin Dashboard**: Review and refine recommendations for RLHF training

## Tech Stack

### Frontend
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui components
- Zustand (state management)

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy (async)
- PostgreSQL
- Redis (caching/job queue)
- Alembic (migrations)

### Infrastructure
- Docker Compose (local development)
- Vercel (frontend hosting)
- Railway/Render (backend hosting)
- Supabase (database hosting)

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for frontend development without Docker)
- Python 3.11+ (for backend development without Docker)

### Quick Start with Docker

1. Clone the repository:
```bash
git clone https://github.com/yourusername/shoe-matcher.git
cd shoe-matcher
```

2. Start all services:
```bash
docker-compose up -d
```

3. Run database migrations:
```bash
docker-compose exec api alembic upgrade head
```

4. Seed the database:
```bash
docker-compose exec api python scripts/seed_data.py
```

5. Access the application:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/v1/docs

### Development without Docker

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database credentials

# Run migrations
alembic upgrade head

# Seed data
python scripts/seed_data.py

# Start server
uvicorn main:app --reload
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Set up environment
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/v1" > .env.local

# Start development server
npm run dev
```

## Project Structure

```
shoe-matcher/
├── frontend/                 # Next.js frontend
│   ├── src/
│   │   ├── app/             # App Router pages
│   │   │   ├── quiz/        # Quiz flow
│   │   │   ├── results/     # Results page
│   │   │   └── admin/       # Admin dashboard
│   │   ├── components/      # UI components
│   │   ├── lib/             # API client, utilities
│   │   └── store/           # Zustand stores
│   └── package.json
│
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── api/             # API routes
│   │   ├── core/            # Config, database, security
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   ├── scrapers/        # Web scrapers
│   │   └── tasks/           # Background tasks
│   ├── alembic/             # Database migrations
│   ├── scripts/             # Utility scripts
│   └── requirements.txt
│
├── docker-compose.yml
└── README.md
```

## API Endpoints

### Public
- `POST /v1/quiz/start` - Start quiz session
- `POST /v1/quiz/{session_id}/answer` - Submit answer
- `POST /v1/quiz/{session_id}/recommend` - Get recommendations
- `GET /v1/shoes` - List shoes
- `GET /v1/shoes/{id}` - Get shoe details

### Admin (requires authentication)
- `POST /v1/admin/login` - Admin login
- `GET /v1/admin/recommendations` - Review queue
- `POST /v1/admin/recommendations/{id}/review` - Review recommendation
- `GET /v1/admin/shoes` - Manage shoes
- `POST /v1/admin/scrape/trigger` - Trigger scraping job

## Environment Variables

### Backend
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://localhost:6379
JWT_SECRET=your-secret-key
ANTHROPIC_API_KEY=sk-ant-xxx  # For AI review parsing
```

### Frontend
```
NEXT_PUBLIC_API_URL=http://localhost:8000/v1
```

## Default Admin Credentials

After running `seed_data.py`:
- Email: `admin@shoematcher.com`
- Password: `admin123`

**Change these in production!**

## License

MIT
