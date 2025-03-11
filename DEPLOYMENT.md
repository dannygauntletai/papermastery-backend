# Deployment Guide for ArXiv Mastery Backend

This document provides instructions for deploying the ArXiv Mastery backend to various platforms, with a focus on Render.

## Prerequisites

Before deploying, ensure you have:

1. A Supabase account and project set up with the required tables (see database_schema.md)
2. A Pinecone account with an index named "arxiv-chunks" created
3. All necessary API keys (Supabase, Pinecone)

## Deploying to Render

### Automatic Deployment

1. Push your code to a GitHub repository
2. Log in to Render (https://render.com)
3. Click "New" and select "Blueprint"
4. Connect your GitHub repository
5. Render will automatically detect the `render.yaml` file and set up the services

### Manual Deployment

1. Log in to Render (https://render.com)
2. Click "New" and select "Web Service"
3. Connect your GitHub repository
4. Configure the service:
   - Name: arxiv-mastery-api
   - Environment: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables:
   - SUPABASE_URL: [Your Supabase URL]
   - SUPABASE_KEY: [Your Supabase service key]
   - PINECONE_API_KEY: [Your Pinecone API key]
   - PINECONE_ENVIRONMENT: us-west1-gcp
   - PINECONE_INDEX: arxiv-chunks
   - APP_ENV: production
6. Click "Create Web Service"

## Environment Variables

Ensure the following environment variables are set in your deployment environment:

- `SUPABASE_URL`: URL to your Supabase project
- `SUPABASE_KEY`: Service key for Supabase
- `PINECONE_API_KEY`: API key for Pinecone
- `PINECONE_ENVIRONMENT`: Environment for Pinecone (e.g., "us-west1-gcp")
- `PINECONE_INDEX`: Name of the Pinecone index (default: "arxiv-chunks")
- `ARXIV_API_BASE_URL`: URL for the arXiv API (default: "http://export.arxiv.org/api/query")
- `OPENALEX_API_BASE_URL`: URL for the OpenAlex API (default: "https://api.openalex.org/works")
- `LOG_LEVEL`: Logging level (default: "INFO")
- `APP_ENV`: Application environment ("development", "testing", or "production")

## Docker Deployment

You can also deploy the application using Docker:

1. Build the Docker image:
   ```bash
   docker build -t arxiv-mastery-api .
   ```

2. Run the container:
   ```bash
   docker run -p 8000:8000 --env-file .env arxiv-mastery-api
   ```

## Local Development with Docker Compose

For local development with Docker Compose:

1. Ensure you have Docker and Docker Compose installed
2. Set up your `.env` file with the required environment variables
3. Run:
   ```bash
   docker-compose up
   ```
4. The API will be available at http://localhost:8000

## Verifying Deployment

After deployment, you can verify that the API is running by:

1. Accessing the root endpoint: `https://your-deployment-url/`
2. Checking the API documentation: `https://your-deployment-url/docs`
3. Using the health check endpoint: `https://your-deployment-url/`

## Troubleshooting

If you encounter issues with deployment:

1. Check the logs in your deployment platform
2. Verify that all environment variables are correctly set
3. Ensure the Python version is compatible (we use Python 3.9)
4. Check that the database schema in Supabase matches what's expected by the application 