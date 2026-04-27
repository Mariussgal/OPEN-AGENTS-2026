import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
  api_key=os.getenv('AI_GATEWAY_API_KEY'),
  base_url='https://ai-gateway.vercel.sh/v1'
)

print("📡 Appel à la Gateway Vercel...")

try:
    response = client.chat.completions.create(
      model='openai/gpt-4o-mini', # gpt-5.4 n'est pas encore dispo, utilise 4o-mini pour le test
      messages=[{'role': 'user', 'content': 'Explique la réentrance en 10 mots.'}]
    )
    print("🤖 Réponse :", response.choices[0].message.content)
    print("✅ Ça marche !")
except Exception as e:
    print(f"❌ Erreur : {e}")