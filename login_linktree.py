import time
import logging
import undetected_chromedriver as uc
from pathlib import Path
from config.settings import PROJECT_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-8s │ %(message)s")
logger = logging.getLogger("login_linktree")

def main():
    user_data_dir = str(PROJECT_ROOT / "browser_session")
    
    logger.info("Starting undetected_chromedriver to open Linktree...")
    
    # Initialize undetected_chromedriver with our existing user data dir
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--disable-save-password-bubble")
    
    # Launch Chrome
    driver = uc.Chrome(options=options, use_subprocess=True)
    
    try:
        logger.info("Opening Linktree Login...")
        driver.get("https://linktr.ee/login")
        
        logger.info("=========================================================")
        logger.info("BROWSER IS OPEN!")
        logger.info("Please log in to your Linktree Account in the opened window.")
        logger.info("You have 2 minutes to complete the login process.")
        logger.info("=========================================================")
        
        # Wait 120 seconds
        for i in range(120, 0, -1):
            if i % 10 == 0:
                logger.info(f"{i} seconds remaining...")
            time.sleep(1)
            
        logger.info("Time is up! Saving session and closing...")
        
    except Exception as e:
        logger.error(f"Error during login: {e}")
    finally:
        logger.info("Closing browser...")
        driver.quit()
        logger.info("Linktree Session saved to browser_session!")

if __name__ == "__main__":
    main()
