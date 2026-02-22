# Smart Chef – Shiny for Python (Digital Ocean App Platform)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# App Platform expects 0.0.0.0:8080; PORT env var may be set
EXPOSE 8080
CMD ["sh", "-c", "shiny run app.py -h 0.0.0.0 -p ${PORT:-8080}"]
