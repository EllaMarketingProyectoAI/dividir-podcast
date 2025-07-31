web: python main.py
web: python supabase_upload.py
web: gunicorn main:app
web: gunicorn -w 1 -b 0.0.0.0:8000 main:app --timeout 600
