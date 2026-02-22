# Smart Chef – Shiny for Python (Digital Ocean App Platform)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# App Platform expects 0.0.0.0:8080
# --no-dev-mode: production mode (avoids file watching / dev behavior that can exit early)
# exec: makes shiny PID 1 so container stays alive
EXPOSE 8080
CMD ["sh", "-c", "exec shiny run app.py -h 0.0.0.0 -p 8080 --no-dev-mode"]
