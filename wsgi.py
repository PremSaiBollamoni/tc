from app import app

# WSGI entry point for serverless deployment
application = app

if __name__ == "__main__":
    app.run()