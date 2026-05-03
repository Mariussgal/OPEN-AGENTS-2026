import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
  api_key=os.getenv('AI_GATEWAY_API_KEY'),
  base_url='https://ai-gateway.vercel.sh/v1'
)

print("📡 Calling Vercel Gateway...")

try:
    response = client.chat.completions.create(
      model='openai/gpt-4o-mini', # gpt-5.4 not available yet, use 4o-mini for the test
      messages=[{'role': 'user', 'content': 'Explain reentrancy in 10 words.'}]
    )
    print("🤖 Response:", response.choices[0].message.content)
    print("✅ It works!")
except Exception as e:
    print(f"❌ Erreur : {e}")