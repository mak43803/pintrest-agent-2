# 🚀 24/7 Cloud Server (VPS) Deployment Guide

This guide explains how to deploy your Pinterest AI Agent to a $5–$8/month Windows Virtual Private Server (VPS) so it runs 24/7/365 without keeping your laptop on.

---

## 🛍️ Step 1: Get a Cheap Windows VPS ($5 - $8 / Month)

Top Recommended Providers (Choose any 1):
1. **Contabo Cloud VPS 1** (~$6/month - 4 vCPU, 8GB RAM) -> *Best Value*
2. **Hetzner Cloud CX22** (~$5–$7/month) -> *Fastest European / US Servers*
3. **AWS Lightsail Windows** (~$10/month - 3 months free trial available)

> 💡 **Note:** When buying, select **Windows Server 2022 Datacenter** as the Operating System.

---

## 🖥️ Step 2: Connect to Your VPS from Your Laptop

1. On your Windows laptop, press `Win + R`, type `mstsc`, and hit **Enter** (opens Remote Desktop Connection).
2. Enter the **IP Address** provided by your VPS host and click **Connect**.
3. Enter username `Administrator` and your VPS password.
4. Click **OK** — You are now logged into your remote 24/7 cloud server desktop!

---

## 📁 Step 3: Copy Agent Code & Install Dependencies

1. On your laptop, right-click the project folder `pintrest ai agent 2` -> **Copy**.
2. On your VPS remote desktop, right-click -> **Paste** (copies the entire project in 30 seconds).
3. Open Command Prompt (`cmd`) on the VPS and navigate to the folder:
   ```cmd
   cd "C:\Users\Administrator\Desktop\pintrest ai agent 2"
   ```
4. Install Python dependencies:
   ```cmd
   python -m pip install -r requirements.txt
   python -m playwright install chromium
   ```

---

## ⚡ Step 4: Run 24/7 on Autopilot

Run the main agent script:
```cmd
python main.py
```

Optional: To ensure the agent auto-launches if the VPS reboots:
```cmd
python main.py --setup-startup
```

---

## 🔒 Step 5: Close RDP Connection & Relax

- Simply close the Remote Desktop window.
- The VPS will keep running `python main.py` **24 hours a day, 7 days a week, 365 days a year**!
