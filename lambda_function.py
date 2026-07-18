
import json
import os
import requests
import urllib.parse
import boto3
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# ==========================================
# ENVIRONMENT VARIABLES (set in Lambda config)
# ==========================================
GROQ_API_KEY = os.environ['GROQ_API_KEY']
SENDER_EMAIL = os.environ['SENDER_EMAIL']
RECIPIENT_EMAIL = os.environ['RECIPIENT_EMAIL']
S3_BUCKET = os.environ['S3_BUCKET']

# AWS Clients
s3_client = boto3.client('s3')
ses_client = boto3.client('ses')


def generate_tech_news_script():
    """Generate a tech news script using Groq API (Free - uses Llama 3)"""
    
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%B %d, %Y")
    
    prompt = f"""You are a professional tech news script writer for a YouTube channel.
Write a compelling 2-3 minute tech news script for today ({today}).

Cover the latest trending topics in technology such as:
- AI and machine learning breakthroughs
- New product launches or updates
- Major company announcements
- Cybersecurity news
- Startup funding or acquisitions

Format the script with:
1. An attention-grabbing intro hook
2. 3-4 news stories with smooth transitions
3. A closing with call-to-action

Make it engaging, informative, and suitable for a YouTube audience.
Use a conversational but professional tone."""

    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert tech news scriptwriter for YouTube."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    result = response.json()
    
    script = result['choices'][0]['message']['content']
    return script


def generate_thumbnail_title(script):
    """Generate a short, catchy thumbnail title from the script using Groq"""
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "You generate short, catchy YouTube thumbnail titles. Maximum 4-5 words. Use ALL CAPS. Make it dramatic and click-worthy."
            },
            {
                "role": "user",
                "content": f"Based on this tech news script, generate ONE short catchy thumbnail title (4-5 words max, ALL CAPS):\n\n{script[:500]}"
            }
        ],
        "temperature": 0.9,
        "max_tokens": 20
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    result = response.json()
    
    title = result['choices'][0]['message']['content'].strip().strip('"')
    return title


def generate_thumbnail(title_text):
    """Generate YouTube thumbnail using Pollinations.ai (FREE - No API Key Needed)"""
    
    prompt = (
        f"Professional YouTube thumbnail for tech news video, "
        f"bold large white text '{title_text}' centered, "
        f"futuristic technology background, neon blue and purple colors, "
        f"circuit board patterns, holographic elements, "
        f"dramatic cinematic lighting, high contrast, 4K quality, eye-catching"
    )
    
    # Pollinations.ai - Completely FREE, no API key, no signup
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1280&height=720&nologo=true"
    
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    
    return response.content


def upload_to_s3(image_bytes, script, title):
    """Upload thumbnail and script to S3"""
    
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")
    
    # Upload thumbnail image
    image_key = f"tech-news/{today}/thumbnail.png"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=image_key,
        Body=image_bytes,
        ContentType='image/png'
    )
    
    # Upload script as text file
    script_key = f"tech-news/{today}/script.txt"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=script_key,
        Body=script.encode('utf-8'),
        ContentType='text/plain'
    )
    
    print(f"Uploaded to S3: {image_key} and {script_key}")
    return image_key, script_key


def send_email(script, image_bytes, title):
    """Send email with the script and thumbnail attached"""
    
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%B %d, %Y")
    
    # Create multipart email
    msg = MIMEMultipart('mixed')
    msg['Subject'] = f"Tech News Ready - {title} ({today})"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL
    
    # HTML body with the script
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
        <h1 style="color: #1a73e8;">Your Daily Tech News is Ready!</h1>
        <h2 style="color: #333;">Thumbnail Title: {title}</h2>
        <p style="color: #666;">Generated on {today}</p>
        <hr style="border: 1px solid #eee;">
        <h3>Script:</h3>
        <div style="background: #f5f5f5; padding: 20px; border-radius: 10px; white-space: pre-wrap; line-height: 1.8;">
{script}
        </div>
        <hr style="border: 1px solid #eee;">
        <p style="color: #666; font-size: 12px;">
            Generated by Tech News Agent | Powered by AWS Lambda + Groq + Pollinations AI
        </p>
    </body>
    </html>
    """
    
    # Attach HTML body
    html_part = MIMEText(html_body, 'html')
    msg.attach(html_part)
    
    # Attach thumbnail image
    image_attachment = MIMEImage(image_bytes, _subtype='png')
    image_attachment.add_header('Content-Disposition', 'attachment', filename='thumbnail.png')
    msg.attach(image_attachment)
    
    # Send via SES
    ses_client.send_raw_email(
        Source=SENDER_EMAIL,
        Destinations=[RECIPIENT_EMAIL],
        RawMessage={'Data': msg.as_string()}
    )
    
    print("Email sent successfully!")


def lambda_handler(event, context):
    """Main Lambda handler - orchestrates the entire agent workflow"""
    
    try:
        print("Tech News Agent Started!")
        
        # Step 1: Generate tech news script
        print("Generating tech news script...")
        script = generate_tech_news_script()
        print(f"Script generated! Length: {len(script)} characters")
        
        # Step 2: Generate thumbnail title
        print("Generating thumbnail title...")
        title = generate_thumbnail_title(script)
        print(f"Thumbnail title: {title}")
        
        # Step 3: Generate thumbnail image
        print("Generating thumbnail image with Pollinations AI...")
        image_bytes = generate_thumbnail(title)
        print(f"Thumbnail generated! Size: {len(image_bytes)} bytes")
        
        # Step 4: Upload to S3
        print("Uploading to S3...")
        image_key, script_key = upload_to_s3(image_bytes, script, title)
        print("Upload complete!")
        
        # Step 5: Send email
        print("Sending email...")
        send_email(script, image_bytes, title)
        print("All done! Email sent successfully!")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Tech News Agent completed successfully!',
                'title': title,
                'script_length': len(script),
                'thumbnail_size': len(image_bytes),
                'date': datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M:%S IST")
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'date': datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")
            })
        }

