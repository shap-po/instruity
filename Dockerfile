# Load python image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file to the container  
COPY requirements.txt .

# Install python dependencies
RUN pip install -r requirements.txt

# Install ffmpeg
RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get install -y ffmpeg

# Copy the content of the local directory to the working directory
COPY . .

# Run the app
CMD ["python", "bot.py"]

