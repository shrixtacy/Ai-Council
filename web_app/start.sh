#!/bin/bash

echo "========================================"
echo "  AI Council Web Application"
echo "========================================"
echo ""

# Check if backend dependencies are installed
echo "[1/3] Checking dependencies..."
python3 -c "import fastapi; import ai_council" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing backend dependencies..."
    cd backend
    pip install -r requirements.txt
    cd ..
fi

# Check for .env file
if [ ! -f "backend/.env" ]; then
    echo ""
    echo "WARNING: No .env file found!"
    echo "Please create backend/.env with your API keys."
    echo "Example:"
    echo "  OPENAI_API_KEY=your_key_here"
    echo "  ANTHROPIC_API_KEY=your_key_here"
    echo ""
    read -p "Press Enter to continue..."
fi

# Start backend
echo ""
echo "[2/3] Starting backend server..."
cd backend
python3 main.py &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start frontend
echo "[3/3] Opening frontend..."
# Start frontend server
echo "[3/3] Starting frontend server..."
cd frontend
python3 -m http.server 8080 &
FRONTEND_PID=$!
cd ..

# Open in browser
sleep 2
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:8080/
elif command -v open > /dev/null; then
    open http://localhost:8080/
else
    echo "Please open http://localhost:8080/ in your browser"
fi

echo ""
echo "========================================"
echo "  AI Council is running!"
echo "========================================"
echo ""
echo "Backend API: http://localhost:8000"
echo "Frontend: http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait $BACKEND_PID
