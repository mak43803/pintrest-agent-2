import asyncio
import sys
import os

# Add current directory to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from browser.browser_manager import BrowserManager
from browser.linktree_client import LinktreeClient


async def main():
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-8s │ %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    print("Initializing BrowserManager...")
    manager = BrowserManager()
    await manager.initialize()

    try:
        print("Initializing LinktreeClient...")
        client = LinktreeClient(manager)

        print("[INFO] Bypassing explicit login check since persistent context is already authenticated.")

        print("Attempting to add a test link to a collection...")
        success = await client.add_link_to_collection(
            title="Rhode Glazing Milk Hydrating Ceramide Facial Essence",
            url="https://www.amazon.com/Glazing-Hydrating-Ceramide-Facial-Essence/dp/B0H7NKZ5TK/ref=sr_1_1?dib=eyJ2IjoiMSJ9.V53iLYDT6icc-8oHdDHZnAjnrIg58wA1OXrr8G7rTR8E-CpUHHDLtq-9sXtYa8f_UqlyFosyxPEJyXEsyHp9iLR-K4lZtT1nwQshGXys_hwnGZxxcESj-whfCVmkz89CGtb3KpIbCa2X9uuDMxiq7rhF8mK3Gk6LKSBX7FawuDZ460WwxD3SYE54dsGhJFyUoDjLBHJ-C7wHSGGTnydDCVxnI8NWnS7TBXze9NKT0Zb6KqUM0P2U2R1G_bzQvSQnXHX6gxrweJQLab_jRRv1VYYQnVBksvJ3IUeQdugH9C4.QkoYpKQX6qHIgDGLXvYuDaXEQ0b8Gj7yih7K7S8nsnE&dib_tag=se&keywords=Rhode+Peptide+Glazing+Fluid&qid=1784420810&sr=8-1&tag=savvyshop0965-20",
            collection_name="Viral skincare routine"
        )
        if success:
            print("[SUCCESS] Link and Collection added successfully!")
        else:
            print("[ERROR] Failed to add link to collection!")

        # Keep browser open for a few seconds so the user can inspect it
        print("Keeping browser open for 15 seconds so you can inspect...")
        await asyncio.sleep(15)

    except Exception as e:
        print(f"[ERROR] Error occurred: {e}")
    finally:
        print("Shutting down browser...")
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
