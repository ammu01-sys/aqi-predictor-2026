import os
import sys
# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


def test_connection():
    print("==================================================")
    print("Testing Hopsworks Connectivity")
    print("==================================================")
    
    # Check if keys are present
    api_key = os.getenv("HOPSWORKS_API_KEY")
    project_name = os.getenv("HOPSWORKS_PROJECT_NAME")
    
    if not api_key:
        print("Error: HOPSWORKS_API_KEY is not set in environment.")
        return
        
    from src.utils import hopsworks_login
    try:
        project = hopsworks_login()
        print("\nLogin Successful!")
        print(f" - Project Name: {project.name}")
        print(f" - Project ID: {project.id}")
        print("Connectivity test PASSED.")
    except Exception as e:
        print(f"\nFailed to connect to Hopsworks: {e}")

if __name__ == "__main__":
    test_connection()
