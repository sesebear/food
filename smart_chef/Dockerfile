# Smart Chef – Shiny for Python (Digital Ocean App Platform)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run with uvicorn directly (Shiny uses uvicorn under the hood)
# This is more reliable in containers than "shiny run"
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]