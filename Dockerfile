FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8347

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["http"]
