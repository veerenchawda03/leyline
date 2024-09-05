# Use an official Python runtime as a parent image
FROM python:3.11

# Set the working directory in the container
WORKDIR /app


COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .


# COPY init-mongo.sh /scripts/init-mongo.sh
# RUN chmod +x /scripts/init-mongo.sh


# Make port 3000 available to the world outside this container
EXPOSE 3000
EXPOSE 27017

# Define environment variable for Flask
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Run the application
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
