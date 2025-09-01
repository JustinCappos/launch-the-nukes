#!/bin/bash
# Local development setup script

set -e

echo "🛠️  Setting up local development environment..."

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+ first."
    exit 1
fi

# Check for Redis
if ! command -v redis-server &> /dev/null; then
    echo "❌ Redis not found. Installing..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install redis
        else
            echo "Please install Homebrew first: https://brew.sh/"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        sudo apt-get update && sudo apt-get install -y redis-server
    else
        echo "Unsupported OS. Please install Redis manually."
        exit 1
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Create .env file for local development
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cat > .env << EOF
# Local development environment variables
DEBUG=true
SECRET_KEY=launch-the-nukes-secret-key-2025-dev
REDIS_URL=redis://localhost:6379/0
NUM_WORKERS=2
HOST=127.0.0.1
PORT=8080
OLLAMA_URL=http://localhost:11434
MCP_CACHE_DURATION=300
JOB_TIMEOUT=300
EOF
    echo "✅ Created .env file. You can edit it to customize your local settings."
fi

# Check if Redis is running
echo "🔴 Checking Redis status..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis is not running. Starting Redis..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS with Homebrew
        brew services start redis
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        sudo systemctl start redis-server
    else
        echo "Please start Redis manually: redis-server"
    fi
    
    # Wait a moment for Redis to start
    sleep 2
    
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis started successfully"
    else
        echo "❌ Failed to start Redis. Please start it manually."
        exit 1
    fi
else
    echo "✅ Redis is running"
fi

# Check for Ollama (optional)
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama not running. This is optional for local development."
    echo "   To install Ollama: https://ollama.ai/"
    echo "   To start Ollama: ollama serve"
fi

echo ""
echo "✅ Local development environment ready!"
echo ""
echo "To start the application:"
echo "  1. Start workers: python worker.py --workers 2"
echo "  2. Start Flask app: python app.py"
echo "  3. Open browser: http://localhost:8080"
echo ""
echo "Useful commands:"
echo "  - Run tests: python -m pytest"
echo "  - Check Redis: redis-cli ping"
echo "  - View Redis data: redis-cli monitor"
