#!/bin/bash
# Local development setup script

set -e

echo "🛠️  Setting up local development environment..."

# -- Check Dependencies, print error if missing --
command -v python3 >/dev/null || MISSING_PYTHON=true
command -v pip3 >/dev/null || MISSING_PIP=true
python3 -m venv --help >/dev/null || MISSING_VENV=true
command -v redis-server >/dev/null || MISSING_REDIS=true

# -- Install Dependencies if Missing --
install_dependencies() {
    if [[ "$OSTYPE" == "darwin" ]]; then
        # python3
        if [[ $MISSING_PYTHON == true ]] || [[ $MISSING_PIP == true ]] || [[ $MISSING_VENV == true ]]; then
            if command -v brew &> /dev/null; then
                echo "📦 Installing Python3 and venv via Homebrew..."
                brew install python
            else
                echo "❌ Homebrew not installed. Please install Homebrew first: https://brew.sh/"
                exit 1
            fi
        fi
        # redis
        if [[ $MISSING_REDIS == true ]]; then
            if command -v brew &> /dev/null; then
                echo "📦 Installing Redis via Homebrew..."
                brew install redis
            else
                echo "❌ Homebrew not installed. Please install Redis manually."
                exit 1
            fi
        fi

    elif [[ "$OSTYPE" == "linux-gnu" ]]; then
        # detect package manager
        if command -v pacman &> /dev/null; then
            PKG_MANAGER="pacman"
        elif command -v apt-get &> /dev/null; then
            PKG_MANAGER="apt"
        elif command -v dnf &> /dev/null; then
            PKG_MANAGER="dnf"
        elif command -v yum &> /dev/null; then
            PKG_MANAGER="yum"
        elif command -v zypper &> /dev/null; then
            PKG_MANAGER="zypper"
        elif command -v apk &> /dev/null; then
            PKG_MANAGER="apk"
        else
            echo "❌ Unsupported Linux distro. Please install python3, pip, venv, and redis manually."
            exit 1
        fi

        echo "Using package manager: $PKG_MANAGER"

        # Install missing packages per package manager
        case "$PKG_MANAGER" in
            pacman)
                [[ $MISSING_PYTHON == true || $MISSING_PIP == true || $MISSING_VENV == true ]] && sudo pacman -Sy --noconfirm python python-pip
                [[ $MISSING_REDIS == true ]] && sudo pacman -Sy --noconfirm redis
                ;;
            apt)
                [[ $MISSING_PYTHON == true || $MISSING_PIP == true || $MISSING_VENV == true ]] && sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
                [[ $MISSING_REDIS == true ]] && sudo apt-get install -y redis-server
                ;;
            dnf)
                [[ $MISSING_PYTHON == true || $MISSING_PIP == true || $MISSING_VENV == true ]] && sudo dnf install -y python3 python3-pip python3-virtualenv
                [[ $MISSING_REDIS == true ]] && sudo dnf install -y redis
                ;;
            yum)
                [[ $MISSING_PYTHON == true || $MISSING_PIP == true || $MISSING_VENV == true ]] && sudo yum install -y python3 python3-pip python3-virtualenv
                [[ $MISSING_REDIS == true ]] && sudo yum install -y redis
                ;;
            zypper)
                [[ $MISSING_PYTHON == true || $MISSING_PIP == true || $MISSING_VENV == true ]] && sudo zypper install -y python3 python3-pip python3-virtualenv
                [[ $MISSING_REDIS == true ]] && sudo zypper install -y redis
                ;;
            apk)
                [[ $MISSING_PYTHON == true || $MISSING_PIP == true || $MISSING_VENV == true ]] && sudo apk add python3 py3-pip py3-virtualenv
                [[ $MISSING_REDIS == true ]] && sudo apk add redis
                ;;
        esac

    else
        echo "❌ Unsupported OS. Please install python3, pip, venv, and redis manually."
        exit 1
    fi

    echo "✅ Installation attempts completed."
}

# Run installer if any missing
if [[ $MISSING_PYTHON == true || $MISSING_PIP == true || $MISSING_VENV == true || $MISSING_REDIS == true ]]; then
    install_dependencies
fi

# -- Verify installations --
command -v python3 >/dev/null || { echo "❌ python3 could not be installed. Please manually install."; exit 1; }
command -v pip3 >/dev/null || { echo "❌ pip3 could not be installed. Please manually install."; exit 1; }
python3 -m venv --help >/dev/null || { echo "❌ venv module could not be installed. Please manually install."; exit 1; }
command -v redis-server >/dev/null || { echo "❌ redis-server could not be installed. Please manually install."; exit 1; }

echo "✅ All package dependencies installed."

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📥 Installing python dependencies..."
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
    echo "⚠️  Redis is not running. Attempting to start..."

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS with Homebrew
        brew services start redis
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux - detect systemd service name
        REDIS_SERVICE="redis-server"
        # check if arch-style service exists
        if systemctl list-unit-files | grep -q '^redis\.service'; then
            REDIS_SERVICE="redis"
        elif systemctl list-unit-files | grep -q '^valkey\.service'; then
            REDIS_SERVICE="valkey"
        fi

        # try to start service
        if ! sudo systemctl start "$REDIS_SERVICE"; then
            echo "⚠️  Initial start failed. Enabling $REDIS_SERVICE and retrying..."
            sudo systemctl enable "$REDIS_SERVICE"
            sleep 1
            if ! sudo systemctl start "$REDIS_SERVICE"; then
                echo "❌ Failed to start Redis. Please start it manually."
                exit 1
            fi
        fi
    else
        echo "Please start Redis manually: redis-server"
        exit 1
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
