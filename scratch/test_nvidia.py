import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv("d:/Project2026/TESTA/.env")
api_key = os.getenv("NVIDIA_API_KEY")

client = OpenAI(
  base_url="https://integrate.api.nvidia.com/v1",
  api_key=api_key
)

models_to_test = [
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama3-70b-instruct",
    "nvidia/nemotron-4-340b-instruct"
]

for model in models_to_test:
    try:
        completion = client.chat.completions.create(
          model=model,
          messages=[{"role":"user","content":"Hello"}],
          max_tokens=10
        )
        print(f"Success with {model}")
        break
    except Exception as e:
        print(f"Failed with {model}: {e}")
