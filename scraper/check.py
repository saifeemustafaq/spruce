import os
import sys

# Ensure the parent directory is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.main import main

if __name__ == "__main__":
    main()
