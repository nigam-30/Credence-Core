FROM python:3.11-slim

# Install g++ compiler and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source files
COPY . .

# Compile C++ backend binary
RUN g++ main.cpp account.cpp credit.cpp debit.cpp fd.cpp loan.cpp report.cpp upi.cpp utils.cpp cheque.cpp globals.cpp -o bank_system

# Expose port
EXPOSE 5000

ENV PORT=5000
ENV PYTHONUNBUFFERED=1

# Start the Flask app
CMD ["python", "flask_app.py"]
