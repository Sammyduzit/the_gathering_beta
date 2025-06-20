# The Gathering 🌲

*A quiet digital clearing where souls meet.*

## What is this?

Sometimes you stumble upon a place that feels just right. The Gathering is one of those places - a virtual space where people can sit together, share thoughts, and simply be present with one another.

Think of it as a collection of rooms, each with its own character. You can join conversations that flow naturally through the space, step aside for private exchanges, or gather in small circles with kindred spirits. Three ways to connect, each serving its purpose in the rhythm of living interaction.

## Getting Started

You'll need Python 3.13+ and PostgreSQL running on your system.

### Quick Setup

```bash
# Clone this space
git clone https://github.com/your-username/the-gathering.git
cd the-gathering

# Set up your environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install what you need
pip install -r requirements.txt

# Configure your database
# Create a PostgreSQL database named 'thegathering'
# Update app/core/config.py with your database URL if needed

# Start the gathering
python main.py
```

The space comes alive at `http://localhost:8000`

### Docker Alternative

If you prefer:
```bash
docker-compose up -d
```

## Exploring the Space

Once everything is running, visit `http://localhost:8000/docs` to see what's possible. The API documentation there lets you try everything directly - no additional tools needed.

### Sample Accounts

The space comes with a few friendly inhabitants already present:
- **testadmin@thegathering.com** (password: `adminpass`) - can create new rooms
- **alice@test.com** (password: `alice123`) - fellow traveler
- **carol@test.com** (password: `carol123`) - another soul in the clearing

Feel free to create your own account and find your place here.

## How it Works

**Rooms** - Different clearings, each with their own energy  
**Public conversations** - Open exchanges visible to everyone in the room  
**Private chats** - Quiet words between two people  
**Group circles** - Small gatherings within the larger space  

Each message finds its way to the right ears.

## Technology

**Backend:** FastAPI 0.115.13 with Python 3.13+  
**Database:** PostgreSQL with SQLAlchemy 2.0  
**Authentication:** JWT with bcrypt password hashing  
**Architecture:** Repository pattern with service layer separation  
**Validation:** Pydantic V2 for request/response models  
**Testing:** pytest with unit/e2e test structure, essential coverage

Key features include composite database indexing for chat performance, XOR constraint message routing for the three conversation types, and dependency injection throughout the API layer.

## Contributing

This is a personal project shared openly. Feel free to look around, learn from it, or suggest improvements. If something speaks to you and you'd like to contribute, I'm open to thoughtful conversations about where this space might grow.

## License

MIT - Use it, learn from it, build upon it as you see fit.

---

*May you find good company in these digital woods.*
