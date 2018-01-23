#!/usr/bin/env python
import os
import sys
import webbrowser

if __name__ == "__main__":
    # Apply settings
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "idp.settings")

    # Test python packages
    try:
        from django.core.management import execute_from_command_line
        import picklefield
        import feedparser
        import lxml
        import requests
        import xlsxwriter
    except ImportError:
        libs = [
            "django==2.0.1",
            "django-picklefield==1.0.0",
            "feedparser==5.2.1",
            "lxml==4.1.1",
            "requests==2.18.4",
            "xlsxwriter==1.0.2"
        ]
        import subprocess
        print("Trying to install libs via pip3:")
        subprocess.run(["pip3", "install", *libs])

    # Start server if no argument was given
    if len(sys.argv) == 1:
        # Check if database and models have been initialized
        if not os.path.exists("db.sqlite3"):
            print("No database found. Creating tables now ...")
            execute_from_command_line(sys.argv + ["makemigrations"])
            execute_from_command_line(sys.argv + ["migrate"])
            from idpscraper.views import init_apartments
            init_apartments()
            print("... Finished creating tables.")
            webbrowser.open_new("http://localhost:8080/idpscraper/apartment_settings")
        sys.argv += ["runserver", "8080"]
    execute_from_command_line(sys.argv)

