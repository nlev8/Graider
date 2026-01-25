#!/bin/bash
# Setup and Run Assignment Grader Web App
# ========================================

echo "📚 Assignment Grader Setup"
echo "=========================="
echo ""

cd "/Users/alexc/Downloads/Assignment Grader"

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install flask flask-cors openai python-docx openpyxl python-dotenv --break-system-packages -q

# Check if web folder exists
if [ ! -d "web" ]; then
    echo "❌ Error: web folder not found!"
    echo "Make sure to copy the 'web' folder to '/Users/alexc/Downloads/Assignment Grader/'"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "Create it with: echo 'OPENAI_API_KEY=your-key-here' > .env"
fi

echo ""
echo "🚀 Starting server..."
echo "📍 Open in browser: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 grader_server.py
